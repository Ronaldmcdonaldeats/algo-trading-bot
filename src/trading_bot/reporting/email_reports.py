"""Email Daily Reports - Automated morning trading summaries

Generates and sends automated daily email reports:
- Trade summaries (buys, sells, P&L)
- Portfolio performance
- Risk metrics
- Next day outlook
- Alerts and anomalies
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


@dataclass
class DailyReport:
    """Daily trading report"""
    date: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    current_equity: float
    starting_equity: float
    daily_return: float
    portfolio_return: float
    portfolio_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    risk_score: float  # 0-100
    alerts: List[str]
    next_day_outlook: str


class EmailReporter:
    """Generate and send daily trading reports"""
    
    def __init__(self, sender_email: Optional[str] = None, 
                 sender_password: Optional[str] = None,
                 cache_dir: str = ".cache"):
        self.sender_email = sender_email or os.getenv('EMAIL_ADDRESS')
        self.sender_password = sender_password or os.getenv('EMAIL_PASSWORD')
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.enabled = bool(self.sender_email and self.sender_password)
        
    def generate_report(self, trade_history: Dict, portfolio_metrics: Dict,
                       risk_metrics: Dict) -> DailyReport:
        """Generate daily report from trade and portfolio data"""
        
        trades_today = [t for t in trade_history.get('trades', []) 
                       if t.get('date', '').startswith(datetime.now().strftime('%Y-%m-%d'))]
        
        winning = [t for t in trades_today if t.get('pnl', 0) > 0]
        losing = [t for t in trades_today if t.get('pnl', 0) < 0]
        
        total_pnl = sum(t.get('pnl', 0) for t in trades_today)
        win_rate = len(winning) / len(trades_today) if trades_today else 0
        
        avg_win = sum(t.get('pnl', 0) for t in winning) / len(winning) if winning else 0
        avg_loss = sum(t.get('pnl', 0) for t in losing) / len(losing) if losing else 0
        
        largest_win = max((t.get('pnl', 0) for t in trades_today), default=0)
        largest_loss = min((t.get('pnl', 0) for t in trades_today), default=0)
        
        starting_equity = portfolio_metrics.get('starting_equity', 100000)
        current_equity = portfolio_metrics.get('current_equity', 100000)
        daily_return = (current_equity - starting_equity) / starting_equity if starting_equity > 0 else 0
        
        # Risk assessment
        max_dd = risk_metrics.get('max_drawdown', 0)
        volatility = portfolio_metrics.get('volatility', 0)
        risk_score = min(100, abs(max_dd) * 100 + volatility * 20)
        
        # Generate alerts
        alerts = self._generate_alerts(trades_today, total_pnl, win_rate, max_dd)
        
        # Outlook
        outlook = self._generate_outlook(trades_today, win_rate, risk_score)
        
        return DailyReport(
            date=datetime.now().strftime('%Y-%m-%d'),
            total_trades=len(trades_today),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl=total_pnl,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            current_equity=current_equity,
            starting_equity=starting_equity,
            daily_return=daily_return,
            portfolio_return=portfolio_metrics.get('total_return', 0),
            portfolio_volatility=volatility,
            sharpe_ratio=portfolio_metrics.get('sharpe_ratio', 0),
            max_drawdown=max_dd,
            risk_score=risk_score,
            alerts=alerts,
            next_day_outlook=outlook
        )
    
    def _generate_alerts(self, trades: List[Dict], total_pnl: float, 
                        win_rate: float, max_dd: float) -> List[str]:
        """Generate trading alerts based on performance"""
        
        alerts = []
        
        if len(trades) == 0:
            alerts.append("No trades executed today")
        
        if total_pnl < -100:
            alerts.append(f"Large daily loss: ${total_pnl:,.2f}")
        
        if win_rate < 0.3 and len(trades) >= 5:
            alerts.append(f"Low win rate: {win_rate*100:.1f}%")
        
        if max_dd < -0.10:
            alerts.append(f"Significant drawdown: {max_dd*100:.1f}%")
        
        # Consecutive losses
        if len(trades) >= 3:
            recent_pnl = [t.get('pnl', 0) for t in trades[-3:]]
            if all(p < 0 for p in recent_pnl):
                alerts.append("3 consecutive losing trades")
        
        if not alerts:
            alerts.append("Trading day performing as expected")
        
        return alerts
    
    def _generate_outlook(self, trades: List[Dict], win_rate: float, 
                         risk_score: float) -> str:
        """Generate next day outlook"""
        
        if risk_score > 75:
            return "HIGH RISK - Consider reducing position sizes or taking a break"
        elif risk_score > 50:
            return "MODERATE RISK - Monitor positions closely and be ready to reduce"
        elif win_rate > 0.6:
            return "Strong momentum continues - maintain current strategy"
        elif win_rate > 0.4:
            return "Normal trading conditions - continue with normal position sizing"
        else:
            return "Consider strategy adjustment or reduced trading"
    
    def format_html_report(self, report: DailyReport) -> str:
        """Format report as HTML email"""
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #1e3a8a; color: white; padding: 20px; }}
                .section {{ margin: 20px 0; padding: 15px; border-left: 4px solid #3b82f6; }}
                .metric {{ display: inline-block; width: 45%; margin: 10px 2%; }}
                .positive {{ color: #10b981; }}
                .negative {{ color: #ef4444; }}
                .neutral {{ color: #6b7280; }}
                .alert {{ background-color: #fef3c7; padding: 10px; margin: 5px 0; border-radius: 5px; }}
                .risk_high {{ background-color: #fee2e2; }}
                .risk_moderate {{ background-color: #fef3c7; }}
                .risk_low {{ background-color: #dcfce7; }}
                table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f3f4f6; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Daily Trading Report</h1>
                <p>Date: {report.date}</p>
            </div>
            
            <div class="section">
                <h2>Trading Performance</h2>
                <div class="metric">
                    <strong>Total Trades:</strong> {report.total_trades}
                </div>
                <div class="metric">
                    <strong>Win Rate:</strong> <span class="positive">{report.win_rate*100:.1f}%</span>
                </div>
                <div class="metric">
                    <strong>Winning Trades:</strong> {report.winning_trades}
                </div>
                <div class="metric">
                    <strong>Losing Trades:</strong> {report.losing_trades}
                </div>
                <div class="metric">
                    <strong>Daily P&L:</strong> <span class="{'positive' if report.total_pnl > 0 else 'negative'}">
                        ${report.total_pnl:,.2f}
                    </span>
                </div>
                <div class="metric">
                    <strong>Daily Return:</strong> <span class="{'positive' if report.daily_return > 0 else 'negative'}">
                        {report.daily_return*100:.2f}%
                    </span>
                </div>
            </div>
            
            <div class="section">
                <h2>Portfolio Metrics</h2>
                <table>
                    <tr>
                        <td><strong>Current Equity:</strong></td>
                        <td>${report.current_equity:,.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Portfolio Return:</strong></td>
                        <td class="{'positive' if report.portfolio_return > 0 else 'negative'}">
                            {report.portfolio_return*100:.2f}%
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Volatility:</strong></td>
                        <td>{report.portfolio_volatility*100:.2f}%</td>
                    </tr>
                    <tr>
                        <td><strong>Sharpe Ratio:</strong></td>
                        <td>{report.sharpe_ratio:.2f}</td>
                    </tr>
                    <tr>
                        <td><strong>Max Drawdown:</strong></td>
                        <td class="negative">{report.max_drawdown*100:.2f}%</td>
                    </tr>
                </table>
            </div>
            
            <div class="section risk_{'high' if report.risk_score > 75 else 'moderate' if report.risk_score > 50 else 'low'}">
                <h2>Risk Assessment</h2>
                <strong>Risk Score:</strong> {report.risk_score:.1f}/100
                <p>{report.next_day_outlook}</p>
            </div>
            
            <div class="section">
                <h2>Alerts</h2>
                {''.join(f'<div class="alert">{alert}</div>' for alert in report.alerts)}
            </div>
            
            <div class="section">
                <h2>Trade Details</h2>
                <p>Average Win: ${report.avg_win:,.2f}</p>
                <p>Average Loss: ${report.avg_loss:,.2f}</p>
                <p>Largest Win: ${report.largest_win:,.2f}</p>
                <p>Largest Loss: ${report.largest_loss:,.2f}</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_report(self, report: DailyReport, recipient_email: str) -> bool:
        """Send report via email"""
        
        if not self.enabled:
            logger.warning("Email not configured - skipping send")
            return False
        
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = f"Trading Report - {report.date}"
            message["From"] = self.sender_email
            message["To"] = recipient_email
            
            html = self.format_html_report(report)
            message.attach(MIMEText(html, "html"))
            
            # Connect and send
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, message.as_string())
            
            logger.info(f"Report sent to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def save_report(self, report: DailyReport, filename: str = "daily_report.json"):
        """Save report to JSON"""
        
        filepath = self.cache_dir / f"reports_{datetime.now().year}" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'date': report.date,
            'total_trades': report.total_trades,
            'winning_trades': report.winning_trades,
            'losing_trades': report.losing_trades,
            'total_pnl': report.total_pnl,
            'win_rate': report.win_rate,
            'avg_win': report.avg_win,
            'avg_loss': report.avg_loss,
            'largest_win': report.largest_win,
            'largest_loss': report.largest_loss,
            'current_equity': report.current_equity,
            'daily_return': report.daily_return,
            'portfolio_return': report.portfolio_return,
            'volatility': report.portfolio_volatility,
            'sharpe_ratio': report.sharpe_ratio,
            'max_drawdown': report.max_drawdown,
            'risk_score': report.risk_score,
            'alerts': report.alerts,
            'outlook': report.next_day_outlook
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Daily report saved to {filepath}")
        return str(filepath)
