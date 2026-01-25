"""
Advanced Analytics & Reporting Module
Performs P&L attribution, correlation analysis, drawdown analysis,
tax loss harvesting, and generates HTML reports.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

import numpy as np
import pandas as pd
from jinja2 import Template

from trading_bot.utils.advanced_analytics import (
    FactorAttributionEngine, CorrelationAnalyzer, DrawdownAnalyzer,
    TaxLossHarvester, ReturnDecomposition
)

logger = logging.getLogger(__name__)


@dataclass
class AnalyticsConfig:
    """Analytics configuration"""
    trades_file: str
    start_date: str
    end_date: str
    risk_free_rate: float = 0.02
    tax_rate: float = 0.20
    holding_period_for_tax: int = 365  # Long-term capital gains threshold


@dataclass
class AttributionAnalysis:
    """Factor attribution results"""
    momentum_contribution: float
    mean_reversion_contribution: float
    volatility_contribution: float
    market_timing_contribution: float
    security_selection_contribution: float
    total_return: float


@dataclass
class CorrelationAnalysis:
    """Correlation matrix and analysis"""
    symbols: List[str]
    correlation_matrix: np.ndarray
    avg_correlation: float
    max_correlation: Tuple[str, str, float]
    min_correlation: Tuple[str, str, float]
    diversification_ratio: float


@dataclass
class TaxOpportunity:
    """Tax loss harvesting opportunity"""
    symbol: str
    quantity: int
    cost_basis: float
    current_price: float
    unrealized_loss: float
    holding_period_days: int
    is_long_term: bool
    wash_sale_risk: bool


@dataclass
class DrawdownEvent:
    """Single drawdown event"""
    start_date: str
    end_date: str
    duration_days: int
    max_drawdown: float
    recovery_time_days: Optional[int]
    cause: str


class AnalyticsEngine:
    """Main analytics execution engine"""

    def __init__(self, config: AnalyticsConfig):
        self.config = config
        self.trades = self._load_trades()
        self.results_dir = Path("analytics_results")
        self.results_dir.mkdir(exist_ok=True)

    def _load_trades(self) -> pd.DataFrame:
        """Load trades from file"""
        try:
            trades = pd.read_csv(self.config.trades_file)
            trades['entry_date'] = pd.to_datetime(trades['entry_date'])
            trades['exit_date'] = pd.to_datetime(trades['exit_date'])
            return trades
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            return pd.DataFrame()

    def run_full_analysis(self) -> Dict:
        """Run comprehensive analytics pipeline"""
        results = {}

        # 1. Factor Attribution
        logger.info("Running factor attribution analysis...")
        results['attribution'] = self._analyze_attribution()

        # 2. Correlation Analysis
        logger.info("Running correlation analysis...")
        results['correlation'] = self._analyze_correlation()

        # 3. Drawdown Analysis
        logger.info("Running drawdown analysis...")
        results['drawdowns'] = self._analyze_drawdowns()

        # 4. Tax Loss Harvesting
        logger.info("Running tax analysis...")
        results['tax_opportunities'] = self._analyze_tax_opportunities()

        # 5. Return Decomposition
        logger.info("Running return decomposition...")
        results['decomposition'] = self._analyze_returns()

        # Generate reports
        self._generate_html_report(results)
        self._generate_json_report(results)

        return results

    def _analyze_attribution(self) -> Dict:
        """Perform factor attribution analysis"""
        if self.trades.empty:
            return {}

        engine = FactorAttributionEngine()
        
        # Convert trades to format expected by attribution engine
        trades_list = []
        for _, row in self.trades.iterrows():
            trades_list.append({
                'symbol': row.get('symbol', 'UNKNOWN'),
                'qty': row['quantity'],
                'entry': row['entry_price'],
                'exit': row['exit_price']
            })

        attribution = engine.calculate_attribution(trades_list)

        return {
            'by_symbol': attribution.get('by_symbol', {}),
            'by_sector': attribution.get('by_sector', {}),
            'top_contributors': self._get_top_contributors(trades_list),
            'underperformers': self._get_underperformers(trades_list)
        }

    @staticmethod
    def _get_top_contributors(trades: List[Dict]) -> List[Dict]:
        """Get top performing trades"""
        pnl_list = [
            {
                'symbol': t['symbol'],
                'pnl': t['qty'] * (t['exit'] - t['entry']),
                'return_pct': (t['exit'] - t['entry']) / t['entry'] * 100
            }
            for t in trades
        ]
        return sorted(pnl_list, key=lambda x: x['pnl'], reverse=True)[:5]

    @staticmethod
    def _get_underperformers(trades: List[Dict]) -> List[Dict]:
        """Get worst performing trades"""
        pnl_list = [
            {
                'symbol': t['symbol'],
                'pnl': t['qty'] * (t['exit'] - t['entry']),
                'return_pct': (t['exit'] - t['entry']) / t['entry'] * 100
            }
            for t in trades
        ]
        return sorted(pnl_list, key=lambda x: x['pnl'])[:5]

    def _analyze_correlation(self) -> Dict:
        """Perform correlation analysis"""
        if self.trades.empty:
            return {}

        # Get unique symbols
        symbols = self.trades['symbol'].unique() if 'symbol' in self.trades.columns else []
        
        if len(symbols) < 2:
            return {'symbols': list(symbols), 'note': 'Not enough symbols for correlation'}

        # Create synthetic return series
        returns_dict = {}
        for symbol in symbols:
            symbol_trades = self.trades[self.trades['symbol'] == symbol]
            if not symbol_trades.empty:
                returns_dict[symbol] = symbol_trades['return_pct'].values

        analyzer = CorrelationAnalyzer()
        
        # Create DataFrame with equal-length returns
        max_len = max(len(v) for v in returns_dict.values()) if returns_dict else 1
        for symbol in returns_dict:
            returns_dict[symbol] = np.pad(
                returns_dict[symbol],
                (0, max_len - len(returns_dict[symbol])),
                mode='constant',
                constant_values=np.nan
            )

        returns_df = pd.DataFrame(returns_dict)
        correlation = analyzer.analyze(returns_df)

        return {
            'symbols': list(symbols),
            'correlation_matrix': correlation.to_dict(),
            'avg_correlation': float(correlation.values[np.triu_indices_from(correlation.values, k=1)].mean()),
            'well_diversified': float(correlation.values[np.triu_indices_from(correlation.values, k=1)].mean()) < 0.6
        }

    def _analyze_drawdowns(self) -> Dict:
        """Analyze drawdown events"""
        if self.trades.empty:
            return {'events': []}

        analyzer = DrawdownAnalyzer()
        
        # Calculate cumulative returns
        if 'return_pct' in self.trades.columns:
            returns = self.trades['return_pct'].values / 100
            dd_events = analyzer.analyze(returns)
        else:
            dd_events = []

        return {
            'total_events': len(dd_events),
            'avg_duration_days': np.mean([e.get('duration_days', 0) for e in dd_events]) if dd_events else 0,
            'max_drawdown_event': max(dd_events, key=lambda x: x.get('drawdown', 0)) if dd_events else {},
            'recovery_rate': self._calculate_recovery_rate(dd_events)
        }

    @staticmethod
    def _calculate_recovery_rate(events: List[Dict]) -> float:
        """Calculate recovery rate from drawdowns"""
        if not events:
            return 0.0
        
        recovered = [e for e in events if e.get('recovery_time_days') is not None]
        return len(recovered) / len(events) if events else 0.0

    def _analyze_tax_opportunities(self) -> Dict:
        """Identify tax loss harvesting opportunities"""
        if self.trades.empty:
            return {'opportunities': []}

        harvester = TaxLossHarvester()
        
        # Build position dict from trades
        positions = {}
        if 'symbol' in self.trades.columns:
            for symbol in self.trades['symbol'].unique():
                symbol_trades = self.trades[self.trades['symbol'] == symbol]
                if not symbol_trades.empty:
                    last_trade = symbol_trades.iloc[-1]
                    positions[symbol] = {
                        'cost_basis': last_trade['entry_price'] * last_trade['quantity'],
                        'current_price': last_trade['exit_price'],
                        'quantity': last_trade['quantity']
                    }

        opportunities = harvester.identify_opportunities(positions)

        # Calculate metrics
        total_losses = sum(
            opp.get('unrealized_loss', 0) 
            for opp in opportunities
        )

        tax_benefit = total_losses * self.config.tax_rate

        return {
            'opportunities': opportunities,
            'total_losses': total_losses,
            'tax_benefit': tax_benefit,
            'count': len(opportunities)
        }

    def _analyze_returns(self) -> Dict:
        """Perform return decomposition"""
        if self.trades.empty:
            return {}

        # Calculate overall metrics
        total_trades = len(self.trades)
        winning_trades = len(self.trades[self.trades['pnl'] > 0]) if 'pnl' in self.trades.columns else 0
        losing_trades = total_trades - winning_trades

        avg_winner = self.trades[self.trades['pnl'] > 0]['pnl'].mean() if 'pnl' in self.trades.columns else 0
        avg_loser = abs(self.trades[self.trades['pnl'] <= 0]['pnl'].mean()) if 'pnl' in self.trades.columns else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'profit_factor': avg_winner / avg_loser if avg_loser > 0 else 0,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'expectancy': (winning_trades * avg_winner - losing_trades * avg_loser) / total_trades if total_trades > 0 else 0
        }

    def _generate_html_report(self, results: Dict):
        """Generate HTML report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.results_dir / f"analytics_report_{timestamp}.html"

        html_content = self._render_html_template(results)
        
        with open(filepath, "w") as f:
            f.write(html_content)
        
        logger.info(f"✓ Saved HTML report: {filepath}")

    @staticmethod
    def _render_html_template(results: Dict) -> str:
        """Render HTML report from template"""
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Trading Analytics Report</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 { color: #1a1a1a; border-bottom: 3px solid #007bff; padding-bottom: 10px; }
        h2 { color: #333; margin-top: 30px; }
        .metric { display: inline-block; margin: 15px 30px 15px 0; }
        .metric-label { color: #666; font-size: 14px; }
        .metric-value { font-size: 24px; font-weight: bold; color: #007bff; }
        .positive { color: #28a745; }
        .negative { color: #dc3545; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th { background-color: #f8f9fa; padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6; }
        td { padding: 10px 12px; border-bottom: 1px solid #dee2e6; }
        tr:hover { background-color: #f8f9fa; }
        .summary { background-color: #f8f9fa; padding: 15px; border-radius: 4px; margin: 20px 0; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Advanced Trading Analytics Report</h1>
        <p>Generated: {{ timestamp }}</p>

        <h2>📈 Return Analysis</h2>
        <div class="summary">
            <div class="metric">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{{ decomposition.total_trades }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">{{ "%.2f"|format(decomposition.win_rate * 100) }}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">{{ "%.2f"|format(decomposition.profit_factor) }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Expectancy</div>
                <div class="metric-value ${{'positive' if decomposition.expectancy > 0 else 'negative'}}">
                    ${{ "%.2f"|format(decomposition.expectancy) }}
                </div>
            </div>
        </div>

        <h2>🎯 Factor Attribution</h2>
        <div class="summary">
            <p><strong>Top Contributors:</strong></p>
            <table>
                <tr><th>Symbol</th><th>P&L</th><th>Return %</th></tr>
                {% for item in attribution.top_contributors %}
                <tr>
                    <td>{{ item.symbol }}</td>
                    <td class="positive">${{ "%.2f"|format(item.pnl) }}</td>
                    <td class="positive">{{ "%.2f"|format(item.return_pct) }}%</td>
                </tr>
                {% endfor %}
            </table>

            <p><strong>Underperformers:</strong></p>
            <table>
                <tr><th>Symbol</th><th>P&L</th><th>Return %</th></tr>
                {% for item in attribution.underperformers %}
                <tr>
                    <td>{{ item.symbol }}</td>
                    <td class="negative">${{ "%.2f"|format(item.pnl) }}</td>
                    <td class="negative">{{ "%.2f"|format(item.return_pct) }}%</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <h2>🔗 Correlation Analysis</h2>
        <div class="summary">
            <div class="metric">
                <div class="metric-label">Avg Correlation</div>
                <div class="metric-value">{{ "%.2f"|format(correlation.avg_correlation) }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Well Diversified</div>
                <div class="metric-value {{ 'positive' if correlation.well_diversified else 'negative' }}">
                    {% if correlation.well_diversified %}✓ Yes{% else %}✗ No{% endif %}
                </div>
            </div>
        </div>

        <h2>📉 Drawdown Analysis</h2>
        <div class="summary">
            <div class="metric">
                <div class="metric-label">Total Drawdown Events</div>
                <div class="metric-value">{{ drawdowns.total_events }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Avg Duration</div>
                <div class="metric-value">{{ "%.0f"|format(drawdowns.avg_duration_days) }} days</div>
            </div>
            <div class="metric">
                <div class="metric-label">Recovery Rate</div>
                <div class="metric-value">{{ "%.1f"|format(drawdowns.recovery_rate * 100) }}%</div>
            </div>
        </div>

        <h2>💰 Tax Loss Harvesting Opportunities</h2>
        <div class="summary">
            <div class="metric">
                <div class="metric-label">Opportunities Found</div>
                <div class="metric-value">{{ tax_opportunities.count }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Losses</div>
                <div class="metric-value negative">${{ "%.2f"|format(tax_opportunities.total_losses) }}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Tax Benefit (@ {{ config.tax_rate * 100 }}%)</div>
                <div class="metric-value positive">${{ "%.2f"|format(tax_opportunities.tax_benefit) }}</div>
            </div>
        </div>

        <div class="footer">
            <p>Report generated: {{ timestamp }}</p>
            <p>This report is for informational purposes only and does not constitute financial advice.</p>
        </div>
    </div>
</body>
</html>
        """

        template = Template(template_str)
        return template.render(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            attribution=results.get('attribution', {}),
            correlation=results.get('correlation', {}),
            drawdowns=results.get('drawdowns', {}),
            tax_opportunities=results.get('tax_opportunities', {}),
            decomposition=results.get('decomposition', {}),
            config={'tax_rate': 0.20}
        )

    def _generate_json_report(self, results: Dict):
        """Generate JSON report for programmatic access"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = self.results_dir / f"analytics_report_{timestamp}.json"

        # Convert numpy arrays to lists for JSON serialization
        def serialize(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.floating):
                return float(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(filepath, "w") as f:
            json.dump(results, f, indent=2, default=serialize)

        logger.info(f"✓ Saved JSON report: {filepath}")


def main():
    """Run analytics pipeline"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Example configuration
    config = AnalyticsConfig(
        trades_file="backtest_results/trades.csv",  # From backtest
        start_date="2020-01-01",
        end_date="2023-12-31",
        risk_free_rate=0.02,
        tax_rate=0.20
    )

    # Run analysis
    engine = AnalyticsEngine(config)
    results = engine.run_full_analysis()

    logger.info("\n" + "=" * 60)
    logger.info("ANALYTICS COMPLETE")
    logger.info("=" * 60)
    logger.info(f"\nReports saved to: {engine.results_dir}/")
    logger.info("\nGenerated Files:")
    logger.info("  - analytics_report_*.html (Visual report)")
    logger.info("  - analytics_report_*.json (Data export)")


if __name__ == "__main__":
    main()
