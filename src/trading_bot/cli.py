from __future__ import annotations

import argparse
import logging
import os
import platform
import subprocess
import sys

from dotenv import load_dotenv


def _parse_symbols(value: str) -> list[str]:
    symbols = [s.strip().upper() for s in str(value).split(",") if s.strip()]
    if not symbols:
        raise SystemExit("--symbols must not be empty")
    return symbols


def _get_nasdaq_symbols(top_n: int = 500) -> list[str]:
    """Get top N NASDAQ stocks by market cap."""
    try:
        from trading_bot.data.nasdaq_symbols import get_nasdaq_symbols
        symbols = get_nasdaq_symbols(top_n=top_n)
        print(f"[INFO] Loaded {len(symbols)} NASDAQ symbols (top {top_n})")
        return symbols
    except Exception as e:
        print(f"[ERROR] Failed to load NASDAQ symbols: {e}")
        print("[INFO] Falling back to default symbols")
        raise SystemExit(f"NASDAQ symbol loading failed: {e}")


def _save_keys_to_env(key: str, secret: str) -> None:
    """Save Alpaca keys to .env file."""
    env_path = ".env"
    try:
        with open(env_path, "a") as f:
            f.write(f"\nAPCA_API_KEY_ID={key}\n")
            f.write(f"APCA_API_SECRET_KEY={secret}\n")
        print(f"[INFO] Saved Alpaca keys to {env_path}. You can now run without --alpaca-key.")
    except Exception as e:
        print(f"[WARN] Failed to save keys to .env: {e}")


def _add_paper_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="configs/default.yaml")
    p.add_argument(
        "--symbols",
        default="AAPL,MSFT,AMZN,AVGO,META,TSLA,GOOGL,GOOG,COST,NFLX,AMD,ADBE,PEP,LIN,CSCO,TMUS,INTC,QCOM,TXN,AMGN,HON,INTU,BKNG,ISRG,CMCSA,SBUX,MDLZ,GILD,VRTX,REGN,ADP,LRCX,ADI,PANW,MU,KLAC,SNPS,CDNS,MELI,CRWD,MAR,PYPL,CSX,ORLY,MNST,CTAS,PCAR,NXPI,WDAY,LULU,ABNB,DXCM,FTNT,ROST,IDXX,KDP,PAYX,ODFL,MCHP,FAST,CPRT,CTVA,BIIB,VRSK,KHC,EA,AEP,EXC,XEL,GFS,WBD,CSGP,DLTR,SIRI,SPY,QQQ",
        help="Comma-separated tickers (e.g. SPY,AAPL,MSFT)",
    )
    p.add_argument("--nasdaq-top-500", action="store_true", help="Trade top 500 NASDAQ stocks instead of --symbols")
    p.add_argument("--nasdaq-top-100", action="store_true", help="Trade top 100 NASDAQ stocks instead of --symbols")
    # For intraday (15m) data, yfinance commonly works best with shorter periods.
    p.add_argument("--period", default="6mo", help="Data period (e.g. 5d, 60d, 1y, 3mo, 6mo)")
    p.add_argument("--interval", default="1d", help="Bar interval (e.g. 5m, 15m, 1h, 1d)")
    p.add_argument("--start-cash", type=float, default=100_000.0)
    p.add_argument("--db", default="data/trades.sqlite", help="SQLite file for event log")
    p.add_argument("--sleep", type=float, default=30.0, help="Seconds between checks (headless)")
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
    p.add_argument("--alpaca-key", help="Alpaca API Key ID")
    p.add_argument("--alpaca-secret", help="Alpaca Secret Key")
    p.add_argument("--ignore-market-hours", action="store_true", help="Trade outside market hours (for testing)")
    p.add_argument("--max-symbols", type=int, default=None, help="Limit number of symbols to trade (memory optimization)")
    p.add_argument("--memory-mode", action="store_true", help="Enable aggressive memory optimizations (smaller batches, fewer indicators)")
    p.add_argument("--launch-monitor", action="store_true", help="Launch log viewer (default is disabled for faster startup)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trading-bot")
    sub = p.add_subparsers(dest="cmd", required=True)

    bt = sub.add_parser("backtest", help="Run historical backtest")
    bt.add_argument("--config", default="configs/default.yaml")
    bt.add_argument(
        "--symbols",
        default="SPY,QQQ,IWM",
        help="Comma-separated tickers (e.g. SPY,AAPL,MSFT)",
    )
    bt.add_argument("--nasdaq-top-500", action="store_true", help="Trade top 500 NASDAQ stocks instead of --symbols")
    bt.add_argument("--nasdaq-top-100", action="store_true", help="Trade top 100 NASDAQ stocks instead of --symbols")
    bt.add_argument("--period", default="1y", help="Historical period (1y, 2y, 5y, max)")
    bt.add_argument("--interval", default="1d", help="Bar interval (1d, 1wk, 1mo)")
    bt.add_argument("--start-cash", type=float, default=100_000.0)
    bt.add_argument("--commission-bps", type=float, default=0.0)
    bt.add_argument("--slippage-bps", type=float, default=0.0)
    bt.add_argument("--min-fee", type=float, default=0.0)
    bt.add_argument(
        "--strategy",
        default="ensemble",
        choices=["ensemble", "mean_reversion_rsi", "momentum_macd_volume", "breakout_atr"],
        help="Trading strategy to backtest"
    )

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
    paper_report.add_argument("--db", default="data/trades.sqlite")
    paper_report.add_argument("--limit", type=int, default=20)

    paper_analytics = paper_sub.add_parser("analytics", help="DuckDB analytics")
    analytics_sub = paper_analytics.add_subparsers(dest="analytics_cmd", required=True)

    analytics_build = analytics_sub.add_parser("build", help="Build DuckDB from SQLite event store")
    analytics_build.add_argument("--db", default="data/trades.sqlite")
    analytics_build.add_argument("--duckdb", default="analytics.duckdb")

    analytics_report = analytics_sub.add_parser("report", help="Report performance from DuckDB")
    analytics_report.add_argument("--duckdb", default="analytics.duckdb")

    # Learning CLI
    learn = sub.add_parser("learn", help="Inspect learning state (while paper trading)")
    learn_sub = learn.add_subparsers(dest="learn_cmd", required=False)

    learn_inspect = learn_sub.add_parser("inspect", help="Show current regime, weights, recent decisions")
    learn_inspect.add_argument("--db", default="data/trades.sqlite")
    learn_inspect.add_argument("--limit", type=int, default=10)

    learn_history = learn_sub.add_parser("history", help="Show regime history")
    learn_history.add_argument("--db", default="data/trades.sqlite")
    learn_history.add_argument("--limit", type=int, default=20)

    learn_decisions = learn_sub.add_parser("decisions", help="Show recent adaptive decisions")
    learn_decisions.add_argument("--db", default="data/trades.sqlite")
    learn_decisions.add_argument("--limit", type=int, default=10)

    learn_metrics = learn_sub.add_parser("metrics", help="Show performance metrics")
    learn_metrics.add_argument("--db", default="data/trades.sqlite")
    learn_metrics.add_argument("--limit", type=int, default=5)

    # Live Trading
    live = sub.add_parser("live", help="Live trading with Alpaca")
    live_sub = live.add_subparsers(dest="live_cmd", required=False)

    live_paper = live_sub.add_parser("paper", help="Paper trading on Alpaca")
    live_paper.add_argument("--config", default="configs/default.yaml")
    live_paper.add_argument("--symbols", default="SPY", help="Comma-separated tickers")
    live_paper.add_argument("--nasdaq-top-500", action="store_true", help="Trade top 500 NASDAQ stocks instead of --symbols")
    live_paper.add_argument("--nasdaq-top-100", action="store_true", help="Trade top 100 NASDAQ stocks instead of --symbols")
    live_paper.add_argument("--period", default="60d")
    live_paper.add_argument("--interval", default="1d")
    live_paper.add_argument("--start-cash", type=float, default=100_000.0)
    live_paper.add_argument("--db", default="data/trades.sqlite")
    live_paper.add_argument("--iterations", type=int, default=0)
    live_paper.add_argument("--no-ui", action="store_true", help="Disable TUI")
    live_paper.add_argument("--alpaca-key", help="Alpaca API Key ID")
    live_paper.add_argument("--alpaca-secret", help="Alpaca Secret Key")

    live_trading = live_sub.add_parser("trading", help="LIVE trading on Alpaca (REAL MONEY)")
    live_trading.add_argument("--config", default="configs/default.yaml")
    live_trading.add_argument("--symbols", default="SPY", help="Comma-separated tickers")
    live_trading.add_argument("--nasdaq-top-500", action="store_true", help="Trade top 500 NASDAQ stocks instead of --symbols")
    live_trading.add_argument("--nasdaq-top-100", action="store_true", help="Trade top 100 NASDAQ stocks instead of --symbols")
    live_trading.add_argument("--period", default="60d")
    live_trading.add_argument("--interval", default="15m")
    live_trading.add_argument("--db", default="data/trades.sqlite")
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
    live_trading.add_argument("--alpaca-key", help="Alpaca API Key ID")
    live_trading.add_argument("--alpaca-secret", help="Alpaca Secret Key")

    # Maintenance CLI
    maintenance = sub.add_parser("maintenance", help="Database and learning maintenance")
    maintenance_sub = maintenance.add_subparsers(dest="maintenance_cmd", required=False)

    maintenance_cleanup = maintenance_sub.add_parser("cleanup", help="Clean up old database events")
    maintenance_cleanup.add_argument("--db", default="data/trades.sqlite")
    maintenance_cleanup.add_argument("--days-keep", type=int, default=7, help="Keep events for N days")
    maintenance_cleanup.add_argument("--dry-run", action="store_true", help="Show what would be deleted")

    maintenance_summary = maintenance_sub.add_parser("summary", help="Show database summary stats")
    maintenance_summary.add_argument("--db", default="data/trades.sqlite")
    maintenance_summary.add_argument("--days", type=int, default=7, help="Lookback N days")

    return p


def _run_paper(args: argparse.Namespace) -> int:
    # Verify Alpaca credentials are set (fail fast if missing)
    api_key = args.alpaca_key or os.getenv("APCA_API_KEY_ID")
    api_secret = args.alpaca_secret or os.getenv("APCA_API_SECRET_KEY")
    
    if not api_key or not api_secret:
        print("!" * 70)
        print("[ERROR] Alpaca API credentials not found.")
        print("REQUIRED: Set environment variables:")
        print("  export APCA_API_KEY_ID=<your-key>")
        print("  export APCA_API_SECRET_KEY=<your-secret>")
        print("  export APCA_API_BASE_URL=https://paper-api.alpaca.markets")
        print("!" * 70)
        return 1
    
    # Save keys to .env if provided via CLI
    if args.alpaca_key and args.alpaca_secret:
        _save_keys_to_env(args.alpaca_key, args.alpaca_secret)
    
    print(f"[OK] Alpaca credentials verified.")

    from trading_bot.paper.runner import run_paper_trading

    # Handle NASDAQ flags
    if getattr(args, 'nasdaq_top_500', False):
        symbols = _get_nasdaq_symbols(top_n=500)
    elif getattr(args, 'nasdaq_top_100', False):
        symbols = _get_nasdaq_symbols(top_n=100)
    else:
        symbols = _parse_symbols(args.symbols)
    
    # Apply memory optimization limit
    if args.max_symbols and len(symbols) > args.max_symbols:
        symbols = symbols[:args.max_symbols]
        print(f"[INFO] Limited symbols to {args.max_symbols} for memory optimization")
    
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
        ignore_market_hours=bool(args.ignore_market_hours),
        memory_mode=bool(args.memory_mode),
    )
    return 0


def _run_backtest(args: argparse.Namespace) -> int:
    """Run historical backtest."""
    from trading_bot.backtest.engine import run_backtest
    from rich.console import Console
    from rich.table import Table

    console = Console()

    console.print("[bold cyan]Historical Backtest[/bold cyan]")
    
    # Handle NASDAQ flags
    if getattr(args, 'nasdaq_top_500', False):
        symbols = _get_nasdaq_symbols(top_n=500)
    elif getattr(args, 'nasdaq_top_100', False):
        symbols = _get_nasdaq_symbols(top_n=100)
    else:
        symbols = _parse_symbols(args.symbols)
    
    console.print(f"Symbols: {', '.join(symbols)}")
    console.print(f"Period: {args.period} | Interval: {args.interval}")
    console.print(f"Capital: ${args.start_cash:,.0f} | Strategy: {args.strategy}")
    console.print()

    try:
        result = run_backtest(
            config_path=args.config,
            symbols=symbols,
            period=args.period,
            interval=args.interval,
            start_cash=float(args.start_cash),
            commission_bps=float(args.commission_bps),
            slippage_bps=float(args.slippage_bps),
            min_fee=float(args.min_fee),
            strategy_mode=args.strategy,
        )

        # Display results
        table = Table(title="Backtest Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Total Return", f"{result.total_return*100:+.2f}%")
        table.add_row("Sharpe Ratio", f"{result.sharpe:.2f}")
        table.add_row("Max Drawdown", f"{result.max_drawdown*100:.2f}%")
        table.add_row("Calmar Ratio", f"{result.calmar:.2f}")
        table.add_row("Win Rate", f"{result.win_rate*100:.1f}%")
        table.add_row("Number of Trades", str(result.num_trades))
        table.add_row("Avg Win", f"{result.avg_win:+.2f}")
        table.add_row("Avg Loss", f"{result.avg_loss:+.2f}")
        table.add_row("Profit Factor", f"{result.profit_factor:.2f}")
        table.add_row("Final Equity", f"${result.final_equity:,.2f}")

        console.print(table)
        console.print()
        console.print(
            f"[green]Backtest completed. "
            f"Return: {result.total_return*100:+.2f}% | "
            f"Sharpe: {result.sharpe:.2f}[/green]"
        )
        return 0

    except Exception as e:
        console.print(f"[red]Backtest failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


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
        
        # Handle NASDAQ flags
        if getattr(args, 'nasdaq_top_500', False):
            symbols = _get_nasdaq_symbols(top_n=500)
        elif getattr(args, 'nasdaq_top_100', False):
            symbols = _get_nasdaq_symbols(top_n=100)
        else:
            symbols = _parse_symbols(args.symbols)
        
        run_live_paper_trading(
            config_path=args.config,
            symbols=symbols,
            period=args.period,
            interval=args.interval,
            start_cash=float(args.start_cash),
            db_path=args.db,
            iterations=int(args.iterations),
            alpaca_key=args.alpaca_key,
            alpaca_secret=args.alpaca_secret,
            ui=not getattr(args, "no_ui", False),
        )
        return 0

    if live_cmd == "trading":
        from trading_bot.live.runner import run_live_real_trading
        
        # Handle NASDAQ flags
        if getattr(args, 'nasdaq_top_500', False):
            symbols = _get_nasdaq_symbols(top_n=500)
        elif getattr(args, 'nasdaq_top_100', False):
            symbols = _get_nasdaq_symbols(top_n=100)
        else:
            symbols = _parse_symbols(args.symbols)
        
        # Double-check user intent
        if not args.enable_live:
            raise SystemExit(
                "Live trading requires --enable-live flag. "
                "This will trade with REAL MONEY. "
                "Are you sure? Use: --enable-live to confirm."
            )
        
        run_live_real_trading(
            config_path=args.config,
            symbols=symbols,
            period=args.period,
            interval=args.interval,
            db_path=args.db,
            iterations=int(args.iterations),
            max_drawdown_pct=float(args.max_drawdown),
            max_daily_loss_pct=float(args.max_daily_loss),
            alpaca_key=args.alpaca_key,
            alpaca_secret=args.alpaca_secret,
        )
        return 0

    raise SystemExit(f"Unknown live subcommand: {live_cmd}")


def _run_maintenance(args: argparse.Namespace) -> int:
    """Run maintenance commands."""
    maintenance_cmd = args.maintenance_cmd or "cleanup"
    
    if maintenance_cmd == "cleanup":
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from trading_bot.db.maintenance import cleanup_database
        
        engine = create_engine(f"sqlite:///{args.db}")
        with Session(engine) as session:
            stats = cleanup_database(
                session,
                days_to_keep=args.days_keep,
                dry_run=args.dry_run,
            )
            
            if args.dry_run:
                print("[DRY-RUN] Would delete:")
                for key, value in stats.items():
                    if key != "dry_run" and key != "cutoff_time":
                        print(f"  {key}: {value}")
                print(f"  Cutoff: {stats['cutoff_time']}")
            else:
                print("[CLEANUP] Deleted:")
                for key, value in stats.items():
                    if key not in ("cutoff_time",):
                        print(f"  {key}: {value}")
                print(f"  Cutoff: {stats['cutoff_time']}")
        return 0
    
    if maintenance_cmd == "summary":
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from trading_bot.db.maintenance import get_learning_summary
        
        engine = create_engine(f"sqlite:///{args.db}")
        with Session(engine) as session:
            summary = get_learning_summary(session, lookback_days=args.days)
            
            print(f"[SUMMARY] Database stats (last {args.days} days):")
            print(f"  Total decisions: {summary['total_decisions']}")
            print(f"  Signal distribution: {summary['signal_distribution']}")
            print(f"  Regime distribution: {summary['regime_distribution']}")
            if summary['latest_weights']:
                print(f"  Latest weights: {summary['latest_weights']}")
        return 0
    
    raise SystemExit(f"Unknown maintenance subcommand: {maintenance_cmd}")


def main(argv: list[str] | None = None) -> int:
    # Load environment variables from .env file
    load_dotenv()

    # Setup logging to file for debugging
    logging.basicConfig(
        filename="bot_debug.log",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filemode="w",
    )
    logging.info("Trading bot started")
    print(f"[INFO] Debug logs are being written to: {os.path.abspath('bot_debug.log')}")

    if sys.version_info < (3, 9):
        try:
            import yfinance
            ver = getattr(yfinance, "__version__", "unknown")
            print(f"[INFO] Running on Python {sys.version_info.major}.{sys.version_info.minor}. Found yfinance {ver}.")
        except (ImportError, TypeError, AttributeError) as e:
            print("!" * 70)
            print(f"WARNING: You are running Python {sys.version_info.major}.{sys.version_info.minor}. This project recommends Python 3.9+.")
            print(f"Dependency check error: {e}")
            print("The error 'TypeError: type object is not subscriptable' is caused by incompatible libraries on Python 3.8.")
            print("To fix this, run:")
            print(f"    {sys.executable} -m pip install \"yfinance<0.2.0\" \"multitasking<0.0.10\"")
            print("!" * 70)
            return 1

    p = build_parser()
    args = p.parse_args(argv)

    if args.cmd == "backtest":
        return _run_backtest(args)

    if args.cmd == "start":
        # Auto-launch log viewer on Windows (non-blocking) if --launch-monitor is provided
        if platform.system() == "Windows" and getattr(args, 'launch_monitor', False):
            print("[INFO] Launching log viewer in separate window...")
            monitor_cmd = (
                f'start "Trading Bot Brain" cmd /k '
                f'"@echo off & mode con: cols=100 lines=40 & '
                f'echo Monitoring Adaptive Learning System... & '
                f'for /L %n in (0,0,0) do ('
                f'cls & '
                f'"{sys.executable}" -m trading_bot learn inspect --db "{args.db}" --limit 10 & '
                f'timeout /t 2 >nul'
                f')"'
            )
            subprocess.Popen(monitor_cmd, shell=True)  # Non-blocking launch

        # Check if user wants Alpaca (keys provided or in env)
        has_alpaca = (
            args.alpaca_key 
            or args.alpaca_secret 
            or "APCA_API_KEY_ID" in os.environ
        )
        if has_alpaca:
            # If keys provided via CLI, save them for future use
            if args.alpaca_key and args.alpaca_secret:
                _save_keys_to_env(args.alpaca_key, args.alpaca_secret)

            print("[INFO] Alpaca keys detected. Switching 'start' to Alpaca Paper Trading mode.")
            args.live_cmd = "paper"
            return _run_live(args)
        return _run_paper(args)

    if args.cmd == "learn":
        return _run_learn(args)

    if args.cmd == "backtest":
        return _run_backtest(args)

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

    if args.cmd == "maintenance":
        return _run_maintenance(args)

    return 2
