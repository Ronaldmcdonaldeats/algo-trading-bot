from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from trading_bot.engine.paper import PaperEngine, PaperEngineUpdate
from trading_bot.schedule.us_equities import (
    MarketSchedule,
    is_market_open,
    next_bar_time,
    to_eastern,
)
from trading_bot.ui.dashboard import DashboardState, render_paper_dashboard

logger = logging.getLogger(__name__)


@dataclass
class PaperTuiState:
    last_update: PaperEngineUpdate | None = None
    equity_state: DashboardState = field(default_factory=lambda: DashboardState(equity_history=[]))
    paused: bool = False
    busy: bool = False


def run_paper_tui(*, engine: PaperEngine, schedule: MarketSchedule) -> int:
    """Run the full-screen TUI.

    This is kept as a small wrapper so the rest of the codebase doesn't need to import
    Textual unless the user actually uses the TUI.
    """

    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.widgets import Footer, Header, Static
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "Textual is not installed. Install with: python -m pip install -e '.[tui]'"
        ) from e

    class _PaperApp(App):
        CSS = """
        #body { height: 1fr; }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("p", "toggle_pause", "Pause/Resume"),
            Binding("r", "force_step", "Force step"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.state = PaperTuiState()
            self._force = True
            self._last_rendered = None  # Track last render to avoid unnecessary updates

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(id="body")
            yield Footer()

        async def on_mount(self) -> None:
            self.set_interval(3.0, self._tick)  # Refresh every 3 seconds instead of 1 (less flicker)
            self._render(status="Starting…")

        def action_toggle_pause(self) -> None:
            self.state.paused = not self.state.paused

        def action_force_step(self) -> None:
            self._force = True

        def _render(self, *, status: str) -> None:
            body = self.query_one("#body", Static)

            # Only update if something actually changed
            render_key = (status, self.state.last_update, self.state.paused, self.state.busy)
            if render_key == self._last_rendered:
                return  # Skip redundant renders
            self._last_rendered = render_key

            status_text = Text(status)
            if self.state.paused:
                status_text.stylize("bold yellow")
            elif self.state.busy:
                status_text.stylize("bold cyan")
            elif "CLOSED" in status or "ERROR" in status:
                status_text.stylize("bold red")
            else:
                status_text.stylize("bold green")

            status_panel = Panel(status_text, title="Status", padding=(0, 1))

            if self.state.last_update is None:
                body.update(status_panel)
                return

            layout = render_paper_dashboard(self.state.last_update, self.state.equity_state)
            body.update(Group(status_panel, layout))

        async def _tick(self) -> None:
            now = datetime.now(tz=timezone.utc)

            if engine.cfg.iterations > 0 and engine.iteration >= engine.cfg.iterations:
                self._render(status=f"DONE: reached iterations={engine.cfg.iterations}")
                self.exit()
                return

            if self.state.busy:
                self._render(status="BUSY: fetching data / stepping engine")
                return

            if self.state.paused:
                nxt = schedule.seconds_until_next(now)
                self._render(status=f"PAUSED: next scheduled step in {int(nxt)}s")
                return

            if schedule.market_hours_only and not is_market_open(now):
                nxt = schedule.next_run_utc or next_bar_time(now, interval=schedule.interval)
                et = to_eastern(nxt)
                delta = int((nxt - now).total_seconds())
                self._render(
                    status=f"MARKET CLOSED: next run {et.strftime('%Y-%m-%d %H:%M %Z')} ({delta}s)"
                )
                return

            due = schedule.due(now)
            secs = schedule.seconds_until_next(now)

            if not due and not self._force:
                self._render(status=f"WAITING: next step in {int(secs)}s")
                return

            self.state.busy = True
            self._render(status="RUNNING: stepping engine")

            try:
                loop = asyncio.get_running_loop()
                update = await loop.run_in_executor(None, engine.step)
                self.state.last_update = update
                schedule.mark_ran(now)
                self._force = False
            except Exception as e:
                logger.exception("Error during engine step")
                self._render(status=f"ERROR: {str(e)[:100]}")
                await asyncio.sleep(5.0)  # Pause longer to let you read the error
                return
            finally:
                self.state.busy = False

            if self.state.last_update is None:
                self._render(status="WAITING: Engine initializing...")
                return

            cnt = len(self.state.last_update.prices)
            if cnt == 0:
                import sys
                if sys.version_info < (3, 9):
                    self._render(status="ERR: Py3.8/yfinance broken. Try 'python -m trading_bot live paper'")
                else:
                    self._render(status="ERROR: No data received. Check internet or try --interval 1d")
            else:
                # Format benchmark string
                bench_str = ""
                if hasattr(self.state.last_update, 'benchmarks') and self.state.last_update.benchmarks:
                    my_ret = self.state.last_update.benchmarks.get("Portfolio", 0.0)
                    parts = [f"Return: {my_ret:+.2%}"]
                    for k, v in self.state.last_update.benchmarks.items():
                        if k != "Portfolio":
                            parts.append(f"{k}: {v:+.2%}")
                    bench_str = " | ".join(parts)
                
                sig_buy = sum(1 for s in self.state.last_update.signals.values() if s == 1)
                status_msg = f"OK: iter={self.state.last_update.iteration} sym={cnt} sig_buy={sig_buy} trades={len(engine.trade_history)}"
                if bench_str:
                    status_msg += f" | {bench_str}"
                self._render(status=status_msg)

    _PaperApp().run()
    return 0
