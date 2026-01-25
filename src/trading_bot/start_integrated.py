"""Start command - Launches the integrated trading bot with all features"""

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def add_start_args(p: argparse.ArgumentParser) -> None:
    """Add arguments for the start command"""
    p.add_argument(
        '--mode',
        choices=['cli', 'web', 'both'],
        default='cli',
        help='Launch mode: cli (command line), web (dashboard), or both'
    )
    p.add_argument(
        '--web-port',
        type=int,
        default=5000,
        help='Port for web dashboard (default: 5000)'
    )
    p.add_argument(
        '--web-host',
        type=str,
        default='127.0.0.1',
        help='Host for web dashboard (default: 127.0.0.1)'
    )
    p.add_argument(
        '--strategy',
        type=str,
        default='DefaultStrategy',
        help='Strategy name (default: DefaultStrategy)'
    )
    p.add_argument(
        '--config',
        type=str,
        default='configs/master_config.ini',
        help='Config file path (default: configs/master_config.ini)'
    )
    p.add_argument(
        '--live',
        action='store_true',
        help='Run in live mode (default: paper trading)'
    )
    p.add_argument(
        '--no-recovery',
        action='store_true',
        help='Disable drawdown recovery system'
    )
    p.add_argument(
        '--no-tuning',
        action='store_true',
        help='Disable auto-tuning system'
    )
    p.add_argument(
        '--no-journal',
        action='store_true',
        help='Disable trade journal'
    )


def run_cli_mode(manager):
    """Run bot in CLI mode"""
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.layout import Layout
    import time
    
    console = Console()
    
    console.print("\n[bold cyan]═══════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]   TRADING BOT - INTEGRATED MODE[/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════[/bold cyan]\n")
    
    console.print(f"[green]✓[/green] Strategy: [cyan]{manager.strategy_name}[/cyan]")
    console.print(f"[green]✓[/green] Mode: [cyan]{'LIVE' if manager.is_running else 'PAPER'}[/cyan]")
    console.print(f"[green]✓[/green] Systems: Journal | Recovery | Tuning | Options\n")
    
    manager.start(live=False)
    
    try:
        while manager.is_running:
            status = manager.get_status()
            
            # Create status table
            table = Table(title="Trading Bot Status", show_header=False, box=None)
            table.add_row("[bold]Equity:[/bold]", f"${status['equity']:,.2f}")
            table.add_row("[bold]Day P&L:[/bold]", f"${status['day_pnl']:,.2f}")
            table.add_row("[bold]Trades:[/bold]", f"{status['day_trades']}")
            table.add_row("[bold]Recovery:[/bold]", 
                         "[green]Normal[/green]" if not status['recovery']['in_recovery'] else "[yellow]Active[/yellow]")
            table.add_row("[bold]Uptime:[/bold]", status['uptime'])
            
            console.clear()
            console.print(table)
            
            time.sleep(5)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        manager.stop()
        console.print("[green]✓[/green] Bot stopped")


def run_web_mode(manager, host='127.0.0.1', port=5000):
    """Run bot with web dashboard"""
    from trading_bot.web_api import TradingBotAPI
    
    print(f"\n{'='*50}")
    print("  TRADING BOT - WEB DASHBOARD")
    print(f"{'='*50}\n")
    
    print(f"[OK] Starting Web Dashboard on http://{host}:{port}")
    print(f"[OK] Strategy: {manager.strategy_name}")
    print(f"[OK] Systems: Journal | Recovery | Tuning | Options\n")
    
    api = TradingBotAPI(config_path=manager.config_path)
    api.bot = manager.bot
    
    manager.start(live=False)
    
    print(f"[OK] Bot started - Dashboard ready at http://{host}:{port}\n")
    
    try:
        api.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        print("\n[OK] Shutting down...")
        manager.stop()
        print("[OK] Bot stopped")


def run_integrated_start(args) -> int:
    """Run integrated bot with all systems"""
    from trading_bot.bot_manager import BotManager
    
    try:
        # Verify config exists
        config_path = args.config
        if not Path(config_path).exists():
            print(f"[ERROR] Config file not found: {config_path}")
            return 1
        
        # Create bot manager
        manager = BotManager(
            strategy_name=args.strategy,
            config_path=config_path
        )
        
        # Disable systems if requested
        if args.no_journal:
            manager.bot.journal = None
            print("[WARN] Trade journal disabled")
        if args.no_recovery:
            manager.bot.recovery_manager = None
            print("[WARN] Drawdown recovery disabled")
        if args.no_tuning:
            manager.bot.auto_tuner = None
            print("[WARN] Auto-tuning disabled")
        
        # Run in selected mode
        if args.mode == 'cli':
            return 0 if run_cli_mode(manager) is None else 1
        elif args.mode == 'web':
            return 0 if run_web_mode(manager, args.web_host, args.web_port) is None else 1
        elif args.mode == 'both':
            import threading
            
            # Start web in separate thread
            web_thread = threading.Thread(
                target=run_web_mode,
                args=(manager, args.web_host, args.web_port),
                daemon=False
            )
            web_thread.start()
            
            # Run CLI in main thread
            run_cli_mode(manager)
            
            return 0
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start integrated trading bot")
    add_start_args(parser)
    args = parser.parse_args()
    sys.exit(run_integrated_start(args))
