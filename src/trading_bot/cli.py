from __future__ import annotations

import argparse


def _parse_symbols(value: str) -> list[str]:
    symbols = [s.strip().upper() for s in str(value).split(",") if s.strip()]
    if not symbols:
        raise SystemExit("--symbols must not be empty")
    return symbols


def _add_paper_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="configs/default.yaml")
    p.add_argument(
        "--symbols",
        default="SPY",
        help="Comma-separated tickers (e.g. SPY,AAPL,MSFT)",
    )
    # For intraday (15m) data, yfinance commonly works best with shorter periods.
    p.add_argument("--period", default="60d", help="Data period (e.g. 5d, 60d, 1y)")
    p.add_argument("--interval", default="15m", help="Bar interval (e.g. 5m, 15m, 1h, 1d)")
    p.add_argument("--start-cash", type=float, default=100_000.0)
    p.add_argument("--db", default="trades.sqlite", help="SQLite file for event log")
    p.add_argument("--sleep", type=float, default=60.0, help="Seconds between checks (headless)")
    p.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="Number of engine steps. 0 = run until you quit.",
    )
    p.add_argument("--no-ui", action="store_true", help="Disable Textual TUI (headless mode)")
    p.add_argument("--commission-bps", type=float, default=0.0)
    p.add_argument("--slippage-bps", type=float, default=0.0)
    p.add_argument("--min-fee", type=float, default=0.0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trading-bot")
    sub = p.add_subparsers(dest="cmd", required=True)

    bt = sub.add_parser("backtest", help="Run a backtest (stub)")
    bt.add_argument("--config", default="configs/default.yaml")

    start = sub.add_parser("start", help="Alias for `paper run`")
    _add_paper_run_args(start)

    paper = sub.add_parser("paper", help="Paper trading")
    # Add paper run args to the parent parser so they work as defaults
    _add_paper_run_args(paper)
    paper_sub = paper.add_subparsers(dest="paper_cmd", required=False)

    paper_run = paper_sub.add_parser("run", help="Run paper trading (Textual TUI by default)")
    _add_paper_run_args(paper_run)

    paper_report = paper_sub.add_parser(
        "report",
        help="Show latest portfolio snapshot and recent fills",
    )
    paper_report.add_argument("--db", default="trades.sqlite")
    paper_report.add_argument("--limit", type=int, default=20)

    paper_analytics = paper_sub.add_parser("analytics", help="DuckDB analytics")
    analytics_sub = paper_analytics.add_subparsers(dest="analytics_cmd", required=True)

    analytics_build = analytics_sub.add_parser("build", help="Build DuckDB from SQLite event store")
    analytics_build.add_argument("--db", default="trades.sqlite")
    analytics_build.add_argument("--duckdb", default="analytics.duckdb")

    analytics_report = analytics_sub.add_parser("report", help="Report performance from DuckDB")
    analytics_report.add_argument("--duckdb", default="analytics.duckdb")

    # Learning CLI
    learn = sub.add_parser("learn", help="Inspect learning state (while paper trading)")
    learn_sub = learn.add_subparsers(dest="learn_cmd", required=False)

    learn_inspect = learn_sub.add_parser("inspect", help="Show current regime, weights, recent decisions")
    learn_inspect.add_argument("--db", default="trades.sqlite")
    learn_inspect.add_argument("--limit", type=int, default=10)

    learn_history = learn_sub.add_parser("history", help="Show regime history")
    learn_history.add_argument("--db", default="trades.sqlite")
    learn_history.add_argument("--limit", type=int, default=20)

    learn_decisions = learn_sub.add_parser("decisions", help="Show recent adaptive decisions")
    learn_decisions.add_argument("--db", default="trades.sqlite")
    learn_decisions.add_argument("--limit", type=int, default=10)

    learn_metrics = learn_sub.add_parser("metrics", help="Show performance metrics")
    learn_metrics.add_argument("--db", default="trades.sqlite")
    learn_metrics.add_argument("--limit", type=int, default=5)

    # Live Trading
    live = sub.add_parser("live", help="Live trading with Alpaca")
    live_sub = live.add_subparsers(dest="live_cmd", required=False)

    live_paper = live_sub.add_parser("paper", help="Paper trading on Alpaca")
    live_paper.add_argument("--config", default="configs/default.yaml")
    live_paper.add_argument("--symbols", default="SPY", help="Comma-separated tickers")
    live_paper.add_argument("--period", default="60d")
    live_paper.add_argument("--interval", default="1d")
    live_paper.add_argument("--start-cash", type=float, default=100_000.0)
    live_paper.add_argument("--db", default="trades.sqlite")
    live_paper.add_argument("--iterations", type=int, default=0)

    live_trading = live_sub.add_parser("trading", help="LIVE trading on Alpaca (REAL MONEY)")
    live_trading.add_argument("--config", default="configs/default.yaml")
    live_trading.add_argument("--symbols", default="SPY", help="Comma-separated tickers")
    live_trading.add_argument("--period", default="60d")
    live_trading.add_argument("--interval", default="15m")
    live_trading.add_argument("--db", default="trades.sqlite")
    live_trading.add_argument("--iterations", type=int, default=0)
    live_trading.add_argument(
        "--enable-live",
        action="store_true",
        required=True,
        help="REQUIRED: Explicitly enable live trading with real money"
    )
    live_trading.add_argument(
        "--max-drawdown",
        type=float,
        default=5.0,
        help="Kill switch at %% drawdown (default: 5%%)"
    )
    live_trading.add_argument(
        "--max-daily-loss",
        type=float,
        default=2.0,
        help="Max loss per day %% (default: 2%%)"
    )

    return p


def _run_paper(args: argparse.Namespace) -> int:
    from trading_bot.paper.runner import run_paper_trading

    symbols = _parse_symbols(args.symbols)
    run_paper_trading(
        config_path=args.config,
        symbols=symbols,
        period=args.period,
        interval=args.interval,
        start_cash=float(args.start_cash),
        db_path=args.db,
        sleep_seconds=float(args.sleep),
        iterations=int(args.iterations),
        ui=not bool(args.no_ui),
        commission_bps=float(args.commission_bps),
        slippage_bps=float(args.slippage_bps),
        min_fee=float(args.min_fee),
    )
    return 0


def _run_learn(args: argparse.Namespace) -> int:
    """Run learning inspection commands."""
    learn_cmd = args.learn_cmd or "inspect"

    if learn_cmd == "inspect":
        from trading_bot.learn.cli import learn_inspect_cmd
        return int(learn_inspect_cmd(db_path=args.db, limit=int(args.limit)))

    if learn_cmd == "history":
        from trading_bot.learn.cli import learn_history_cmd
        return int(learn_history_cmd(db_path=args.db, limit=int(args.limit)))

    if learn_cmd == "decisions":
        from trading_bot.learn.cli import learn_decisions_cmd
        return int(learn_decisions_cmd(db_path=args.db, limit=int(args.limit)))

    if learn_cmd == "metrics":
        from trading_bot.learn.cli import learn_metrics_cmd
        return int(learn_metrics_cmd(db_path=args.db, limit=int(args.limit)))

    raise SystemExit(f"Unknown learn subcommand: {learn_cmd}")


def _run_live(args: argparse.Namespace) -> int:
    """Run live trading on Alpaca."""
    live_cmd = args.live_cmd or "paper"

    if live_cmd == "paper":
        from trading_bot.live.runner import run_live_paper_trading
        
        symbols = _parse_symbols(args.symbols)
        return int(run_live_paper_trading(
            config_path=args.config,
            symbols=symbols,
            period=args.period,
            interval=args.interval,
            start_cash=float(args.start_cash),
            db_path=args.db,
            iterations=int(args.iterations),
        ))

    if live_cmd == "trading":
        from trading_bot.live.runner import run_live_real_trading
        
        symbols = _parse_symbols(args.symbols)
        
        # Double-check user intent
        if not args.enable_live:
            raise SystemExit(
                "Live trading requires --enable-live flag. "
                "This will trade with REAL MONEY. "
                "Are you sure? Use: --enable-live to confirm."
            )
        
        return int(run_live_real_trading(
            config_path=args.config,
            symbols=symbols,
            period=args.period,
            interval=args.interval,
            db_path=args.db,
            iterations=int(args.iterations),
            max_drawdown_pct=float(args.max_drawdown),
            max_daily_loss_pct=float(args.max_daily_loss),
        ))

    raise SystemExit(f"Unknown live subcommand: {live_cmd}")


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)

    if args.cmd == "backtest":
        print("Backtest entrypoint not implemented yet.")
        return 0

    if args.cmd == "start":
        return _run_paper(args)

    if args.cmd == "learn":
        return _run_learn(args)

    if args.cmd == "live":
        return _run_live(args)

    if args.cmd == "paper":
        paper_cmd = args.paper_cmd or "run"

        if paper_cmd == "run":
            return _run_paper(args)

        if paper_cmd == "report":
            from trading_bot.paper.report import paper_report

            return int(paper_report(db_path=args.db, limit=int(args.limit)))

        if paper_cmd == "analytics":
            if args.analytics_cmd == "build":
                from trading_bot.paper.analytics import paper_analytics_build

                return int(paper_analytics_build(db_path=args.db, duckdb_path=args.duckdb))

            if args.analytics_cmd == "report":
                from trading_bot.paper.analytics import paper_analytics_report

                return int(paper_analytics_report(duckdb_path=args.duckdb))

            raise SystemExit(f"Unknown analytics subcommand: {args.analytics_cmd}")

        raise SystemExit(f"Unknown paper subcommand: {paper_cmd}")

    return 2
