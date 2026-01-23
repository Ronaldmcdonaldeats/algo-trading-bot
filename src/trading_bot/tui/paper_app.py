from __future__ import annotations

import asyncio
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
            self._force = False

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(id="body")
            yield Footer()

        async def on_mount(self) -> None:
            self.set_interval(1.0, self._tick)
            self._render(status="Starting…")

        def action_toggle_pause(self) -> None:
            self.state.paused = not self.state.paused

        def action_force_step(self) -> None:
            self._force = True

        def _render(self, *, status: str) -> None:
            body = self.query_one("#body", Static)

            status_text = Text(status)
            if self.state.paused:
                status_text.stylize("bold yellow")
            elif self.state.busy:
                status_text.stylize("bold cyan")
            elif "CLOSED" in status:
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
                update = await asyncio.to_thread(engine.step)
                self.state.last_update = update
                schedule.mark_ran(now)
                self._force = False
            finally:
                self.state.busy = False

            self._render(status=f"OK: last step iter={self.state.last_update.iteration}")

    _PaperApp().run()
    return 0
