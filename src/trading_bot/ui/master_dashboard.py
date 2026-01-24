"""Master Dashboard - Real-time view of all 9 features

Shows in one place:
- Sentiment signals (bullish/bearish by stock)
- Portfolio health (diversification, beta, Sharpe)
- Active orders (brackets, OCO, trailing stops)
- Daily metrics (P&L, win rate, drawdown)
- Risk scores and alerts
- Tax opportunities
- Equity curve trends
"""

from datetime import datetime
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn
from rich.layout import Layout
import logging

logger = logging.getLogger(__name__)


class MasterDashboard:
    """Real-time dashboard for all 9 features"""
    
    def __init__(self):
        self.console = Console()
        self.last_update = None
        
    def render_master_view(self, strategy_data: Dict) -> None:
        """Render complete master dashboard"""
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=2)
        )
        
        layout["header"].update(self._render_header(strategy_data))
        layout["body"].split_row(
            Layout(name="left"),
            Layout(name="right")
        )
        
        layout["left"].split_column(
            Layout(name="sentiment"),
            Layout(name="portfolio"),
            Layout(name="positions")
        )
        
        layout["right"].split_column(
            Layout(name="daily"),
            Layout(name="risk"),
            Layout(name="tax")
        )
        
        # Populate sections
        layout["sentiment"].update(self._render_sentiment_panel(strategy_data))
        layout["portfolio"].update(self._render_portfolio_panel(strategy_data))
        layout["positions"].update(self._render_positions_panel(strategy_data))
        layout["daily"].update(self._render_daily_metrics_panel(strategy_data))
        layout["risk"].update(self._render_risk_panel(strategy_data))
        layout["tax"].update(self._render_tax_panel(strategy_data))
        layout["footer"].update(self._render_footer())
        
        self.console.print(layout)
        self.last_update = datetime.now()
    
    def _render_header(self, data: Dict) -> Panel:
        """Master Dashboard header"""
        
        equity = data.get('current_equity', 100000)
        daily_pnl = data.get('daily_pnl', 0)
        daily_ret = daily_pnl / 100000 * 100
        
        header_text = f"[bold cyan]MASTER INTEGRATED TRADING SYSTEM[/bold cyan] | "
        header_text += f"Equity: [bold yellow]${equity:,.0f}[/bold yellow] | "
        header_text += f"Daily P&L: [bold {'green' if daily_pnl >= 0 else 'red'}]${daily_pnl:,.0f} ({daily_ret:+.2f}%)[/bold] | "
        header_text += f"🤖 All 9 Features Active"
        
        return Panel(header_text, style="bold white on blue")
    
    def _render_sentiment_panel(self, data: Dict) -> Panel:
        """Feature 1: Sentiment signals"""
        
        sentiment_data = data.get('sentiments', {})
        
        table = Table(title="🎯 SENTIMENT SIGNALS", show_header=True)
        table.add_column("Stock", style="cyan")
        table.add_column("Signal", style="magenta")
        table.add_column("Polarity", justify="right")
        table.add_column("Confidence", justify="right")
        table.add_column("Momentum", justify="right")
        
        for symbol, sentiment in list(sentiment_data.items())[:5]:
            signal = sentiment.get('signal', 'NEUTRAL')
            emoji = "🟢" if "BUY" in signal else "🔴" if "SELL" in signal else "⚪"
            polarity = sentiment.get('polarity', 0.0)
            confidence = sentiment.get('confidence', 0.0)
            momentum = sentiment.get('momentum', 0.0)
            
            table.add_row(
                emoji + " " + symbol,
                signal,
                f"{polarity:+.2f}",
                f"{confidence*100:.0f}%",
                f"{momentum:+.2f}"
            )
        
        return Panel(table, style="green")
    
    def _render_portfolio_panel(self, data: Dict) -> Panel:
        """Feature 3: Portfolio health"""
        
        portfolio = data.get('portfolio_health', {})
        
        content = f"""[cyan]Correlation Strength:[/cyan] {portfolio.get('correlation_strength', 'N/A')}
[cyan]Diversification:[/cyan] {portfolio.get('diversification_ratio', 0.0):.2f}
[cyan]Portfolio Beta:[/cyan] {portfolio.get('beta', 1.0):.2f}
[cyan]Concentration:[/cyan] {portfolio.get('concentration', 0.0)*100:.1f}%
[cyan]Sharpe Ratio:[/cyan] [bold yellow]{portfolio.get('sharpe_ratio', 0.0):.2f}[/bold yellow]

[yellow]Recommendation:[/yellow]
{portfolio.get('recommendation', 'Monitor')}"""
        
        return Panel(content, title="📊 PORTFOLIO HEALTH", style="blue")
    
    def _render_positions_panel(self, data: Dict) -> Panel:
        """Feature 7: Active orders and positions"""
        
        positions = data.get('active_positions', {})
        orders = data.get('active_orders', {})
        
        table = Table(title="ACTIVE POSITIONS & ORDERS", show_header=True, pad=(0, 1))
        table.add_column("Type", style="cyan")
        table.add_column("Symbol", style="magenta")
        table.add_column("Size", justify="right")
        table.add_column("Entry", justify="right", style="yellow")
        table.add_column("Current", justify="right")
        table.add_column("P&L", justify="right")
        
        # Active positions
        for symbol, pos in list(positions.items())[:3]:
            entry = pos.get('entry_price', 0)
            current = pos.get('current_price', entry)
            pnl = (current - entry) * pos.get('size', 0)
            pnl_color = "green" if pnl >= 0 else "red"
            
            table.add_row(
                "[green]Position[/green]",
                symbol,
                str(pos.get('size', 0)),
                f"${entry:.2f}",
                f"${current:.2f}",
                f"[{pnl_color}]${pnl:,.0f}[/{pnl_color}]"
            )
        
        # Active orders
        bracket_count = len(orders.get('bracket_orders', []))
        oco_count = len(orders.get('oco_orders', []))
        trailing_count = len(orders.get('trailing_stops', []))
        
        if bracket_count > 0:
            table.add_row("[cyan]Brackets[/cyan]", f"{bracket_count} orders", "", "", "", "")
        if oco_count > 0:
            table.add_row("[cyan]OCO[/cyan]", f"{oco_count} orders", "", "", "", "")
        if trailing_count > 0:
            table.add_row("[cyan]Trailing[/cyan]", f"{trailing_count} stops", "", "", "", "")
        
        return Panel(table, style="magenta")
    
    def _render_daily_metrics_panel(self, data: Dict) -> Panel:
        """Daily trading metrics"""
        
        metrics = data.get('daily_metrics', {})
        
        content = f"""[cyan]Trades Today:[/cyan] {metrics.get('trade_count', 0)}
[cyan]Winning Trades:[/cyan] [green]{metrics.get('winning_trades', 0)}[/green]
[cyan]Losing Trades:[/cyan] [red]{metrics.get('losing_trades', 0)}[/red]
[cyan]Win Rate:[/cyan] [bold]{metrics.get('win_rate', 0)*100:.1f}%[/bold]

[cyan]Daily P&L:[/cyan] [bold yellow]${metrics.get('daily_pnl', 0):+,.0f}[/bold yellow]
[cyan]Portfolio Return:[/cyan] [bold]{metrics.get('portfolio_return', 0)*100:+.2f}%[/bold]
[cyan]Volatility:[/cyan] {metrics.get('volatility', 0)*100:.2f}%"""
        
        return Panel(content, title="📈 DAILY METRICS", style="cyan")
    
    def _render_risk_panel(self, data: Dict) -> Panel:
        """Feature 2: Risk assessment"""
        
        risk = data.get('risk_metrics', {})
        risk_score = risk.get('risk_score', 0)
        
        # Color based on risk
        if risk_score > 75:
            risk_color = "red"
            risk_emoji = "🔴"
            risk_level = "CRITICAL"
        elif risk_score > 50:
            risk_color = "yellow"
            risk_emoji = "🟡"
            risk_level = "CAUTION"
        else:
            risk_color = "green"
            risk_emoji = "🟢"
            risk_level = "OK"
        
        content = f"""[{risk_color}]{risk_emoji} Risk Score: {risk_score:.0f}/100 - {risk_level}[/{risk_color}]

[cyan]Max Drawdown:[/cyan] [red]{risk.get('max_drawdown', 0)*100:.2f}%[/red]
[cyan]Current Drawdown:[/cyan] {risk.get('current_drawdown', 0)*100:.2f}%
[cyan]Days Underwater:[/cyan] {risk.get('underwater_days', 0)}

[yellow]Alert:[/yellow] {risk.get('alert', 'All systems normal')}"""
        
        return Panel(content, title="⚠️  RISK ANALYSIS", style=risk_color)
    
    def _render_tax_panel(self, data: Dict) -> Panel:
        """Feature 6: Tax optimization"""
        
        tax = data.get('tax_data', {})
        opportunities = tax.get('harvest_opportunities', 0)
        year_savings = tax.get('year_savings', 0)
        
        content = f"""[cyan]Tax Loss Opportunities:[/cyan] [bold yellow]{opportunities}[/bold yellow]
[cyan]Potential Tax Savings:[/cyan] [bold green]${tax.get('potential_savings', 0):,.0f}[/bold green]

[cyan]Year-to-Date Savings:[/cyan] ${year_savings:,.0f}
[cyan]Harvests Executed:[/cyan] {tax.get('harvest_count', 0)}

[magenta]💰 Recommendation:[/magenta]
{tax.get('recommendation', 'Monitor for opportunities')}"""
        
        return Panel(content, title="💰 TAX OPTIMIZATION", style="magenta")
    
    def _render_footer(self) -> Panel:
        """Footer with system status"""
        
        status = f"[green]✅ All Systems Active[/green] | Last Update: {datetime.now().strftime('%H:%M:%S')} | "
        status += "[cyan]📊 9 Features Integrated[/cyan] | [yellow]⚡ Real-time Monitoring[/yellow]"
        
        return Panel(status, style="dim white")
    
    def render_trade_alert(self, signal: Dict) -> None:
        """Show prominent trade signal alert"""
        
        symbol = signal.get('symbol', 'UNKNOWN')
        action = signal.get('action', 'HOLD')
        price = signal.get('entry_price', 0)
        confidence = signal.get('confidence', 0)
        reasons = signal.get('reasons', [])
        
        emoji = "🟢 BUY" if action == "BUY" else "🔴 SELL" if action == "SELL" else "⚪ HOLD"
        
        # Build reason list
        reason_text = "[cyan]Reasons:[/cyan]\n"
        for i, reason in enumerate(reasons[:5], 1):
            reason_text += f"  {i}. {reason}\n"
        
        alert = f"""[bold]{emoji}[/bold]

[bold yellow]{symbol}[/bold yellow] @ ${price:.2f}
Confidence: [bold]{confidence*100:.0f}%[/bold]

{reason_text}"""
        
        self.console.print(Panel(alert, style="bold", border_style="yellow"))
    
    def render_summary(self, stats: Dict) -> None:
        """Render strategy summary"""
        
        table = Table(title="📊 STRATEGY SUMMARY", show_header=True, pad=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="yellow")
        
        table.add_row("Total Trades", str(stats.get('total_trades', 0)))
        table.add_row("Win Rate", f"{stats.get('win_rate', 0)*100:.1f}%")
        table.add_row("Sharpe Ratio", f"{stats.get('sharpe_ratio', 0):.2f}")
        table.add_row("Max Drawdown", f"{stats.get('max_drawdown', 0)*100:.2f}%")
        table.add_row("Annual Return", f"{stats.get('annual_return', 0)*100:.2f}%")
        
        self.console.print(Panel(table, style="green"))
