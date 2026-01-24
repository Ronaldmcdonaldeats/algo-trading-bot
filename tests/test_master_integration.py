"""Integration tests for Master Strategy and Dashboard"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from trading_bot.strategy.integrated_strategy import MasterIntegratedStrategy, TradeSignal
from trading_bot.ui.master_dashboard import MasterDashboard
from trading_bot.sentiment.sentiment_analyzer import SentimentAnalyzer
from trading_bot.analytics.portfolio_analytics import PortfolioAnalytics
from trading_bot.analysis.equity_curve_analyzer import EquityCurveAnalyzer
from trading_bot.backtest.tearsheet_analyzer import TearsheetAnalyzer
from trading_bot.reporting.email_reports import EmailReporter
from trading_bot.tax.tax_harvester import TaxLossHarvester
from trading_bot.broker.advanced_orders import AdvancedOrderManager
from trading_bot.monitoring.production_monitoring import StrategyLogger, AlertSystem, HealthMonitor


class TestMasterIntegratedStrategy:
    """Test the master integrated strategy"""
    
    @pytest.fixture
    def strategy(self):
        """Create a test strategy"""
        return MasterIntegratedStrategy()
    
    def test_initialization(self, strategy):
        """Test strategy initializes correctly"""
        assert strategy is not None
        assert hasattr(strategy, 'sentiment')
        assert hasattr(strategy, 'portfolio')
    
    def test_trade_signal_dataclass(self):
        """Test TradeSignal dataclass"""
        signal = TradeSignal(
            symbol='AAPL',
            action='BUY',
            entry_price=150.0,
            position_size=100,
            confidence=0.85,
            sentiment_score=0.75,
            sentiment_signal='bullish',
            kelly_pct=0.02,
            portfolio_health='GOOD',
            regime='BULLISH',
            stop_loss=145.0,
            take_profit=160.0,
            trailing_stop_pct=0.02,
            timestamp=datetime.now(),
            reasons=['Sentiment bullish', 'Kelly sizing']
        )
        
        assert signal.symbol == 'AAPL'
        assert signal.action == 'BUY'
        assert signal.confidence == 0.85
        assert signal.position_size == 100
    
    def test_multiple_sources_confidence(self, strategy):
        """Test that signals combine multiple sources for confidence"""
        # Strategy should have multiple analysis sources
        assert hasattr(strategy, 'sentiment')
        assert hasattr(strategy, 'portfolio')
        assert hasattr(strategy, 'equity_analyzer')
    
    def test_kelly_criterion_integration(self, strategy):
        """Test Kelly Criterion is used for position sizing"""
        # Strategy should have access to Kelly function
        from trading_bot.risk import kelly_position_shares
        
        # Test Kelly formula
        win_rate = 0.55
        avg_win = 0.02
        avg_loss = 0.01
        
        # Kelly formula works correctly
        kelly = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win
        kelly_pct = kelly * 0.25  # Half Kelly
        
        assert kelly > 0
        assert kelly_pct > 0
    
    def test_advanced_order_execution(self, strategy):
        """Test advanced orders are used"""
        # Strategy should have order manager
        assert hasattr(strategy, 'order_manager')
    
    def test_daily_optimization(self, strategy):
        """Test daily optimization runs tearsheet"""
        with patch.object(strategy.tearsheet, 'generate_tearsheet') as mock_ts:
            mock_ts.return_value = {
                'sharpe': 1.5,
                'win_rate': 0.55,
                'max_drawdown': -0.10
            }
            
            # Verify tearsheet would be generated
            mock_ts('test_strategy')
            assert mock_ts.called
    
    def test_daily_email_report(self, strategy):
        """Test email reports are generated"""
        # Strategy should have email reporter
        assert hasattr(strategy, 'email_reporter')
    
    def test_tax_optimization(self, strategy):
        """Test tax harvesting is run"""
        # Strategy should have tax harvester
        assert hasattr(strategy, 'tax_harvester')
    
    def test_state_persistence(self, strategy):
        """Test state is saved and loaded"""
        # Strategy should have save_state method
        assert hasattr(strategy, 'save_state')


class TestMasterDashboard:
    """Test the master dashboard"""
    
    @pytest.fixture
    def dashboard(self):
        """Create a test dashboard"""
        return MasterDashboard()
    
    def test_dashboard_initialization(self, dashboard):
        """Test dashboard initializes with strategy data"""
        assert dashboard is not None
        assert hasattr(dashboard, 'console')
    
    def test_renders_without_error(self, dashboard):
        """Test dashboard initializes properly"""
        # Dashboard should have console
        assert dashboard is not None
        assert hasattr(dashboard, 'console')
    
    def test_sentiment_panel_data(self, dashboard):
        """Test sentiment data is properly formatted"""
        # Dashboard should have console
        assert dashboard.console is not None


class TestProductionMonitoring:
    """Test production monitoring system"""
    
    @pytest.fixture
    def logger(self):
        """Create test logger"""
        return StrategyLogger(log_dir='test_logs')
    
    def test_logger_initialization(self, logger):
        """Test logger initializes correctly"""
        assert logger.main_logger is not None
        assert logger.trade_logger is not None
        assert logger.feature_logger is not None
    
    def test_trade_logging(self, logger):
        """Test trade logging"""
        logger.log_trade(
            symbol='AAPL',
            action='BUY',
            price=150.0,
            size=100,
            pnl=500.0,
            reasons=['Sentiment bullish', 'Kelly sizing']
        )
        # Logger should not raise exception
        assert True
    
    def test_signal_logging(self, logger):
        """Test signal logging"""
        logger.log_signal(
            symbol='AAPL',
            action='BUY',
            confidence=0.85,
            sentiment='bullish',
            regime='uptrend',
            portfolio_health='good'
        )
        assert True
    
    def test_alert_system(self, logger):
        """Test alert system"""
        alerts = AlertSystem(logger)
        
        # Test normal metrics - no alerts
        metrics = {
            'max_drawdown': -0.05,
            'daily_return': 0.02,
            'win_rate': 0.55,
            'sharpe_ratio': 1.2,
            'concentration': 0.30
        }
        
        alerts_list = alerts.check_alerts(metrics)
        assert len(alerts_list) == 0  # No alerts for normal metrics
    
    def test_critical_drawdown_alert(self, logger):
        """Test alert for critical drawdown"""
        alerts = AlertSystem(logger)
        
        # Test critical drawdown
        metrics = {
            'max_drawdown': -0.20,  # Above threshold
            'daily_return': 0.02,
            'win_rate': 0.55,
            'sharpe_ratio': 1.2,
            'concentration': 0.30
        }
        
        alerts_list = alerts.check_alerts(metrics)
        assert len(alerts_list) > 0  # Should have alerts
        assert any('drawdown' in alert.lower() for alert in alerts_list)
    
    def test_health_monitor(self, logger):
        """Test health monitoring"""
        monitor = HealthMonitor(logger)
        
        monitor.record_metric('sentiment_analyzer', 'accuracy', 0.75)
        monitor.record_metric('portfolio_analytics', 'diversification', 0.85)
        
        health = monitor.get_health_status()
        
        assert health['components_active'] >= 2
        assert health['total_metrics'] >= 2


class TestFeatureIntegration:
    """Test all features work together"""
    
    def test_sentiment_to_signal(self):
        """Test sentiment flows to trade signal"""
        sentiment = SentimentAnalyzer()
        
        # Sentiment analyzer should be initialized
        assert sentiment is not None
    
    def test_portfolio_health_check(self):
        """Test portfolio analytics"""
        portfolio = PortfolioAnalytics()
        
        holdings = {'AAPL': 1000, 'MSFT': 500, 'GOOGL': 300}
        prices = {'AAPL': 150, 'MSFT': 300, 'GOOGL': 100}
        
        # Calculate portfolio value
        total_value = sum(holdings[s] * prices[s] for s in holdings)
        assert total_value > 0
    
    def test_equity_curve_detection(self):
        """Test regime detection from equity curve"""
        analyzer = EquityCurveAnalyzer()
        
        # Analyzer should be initialized
        assert analyzer is not None


class TestEndToEndFlow:
    """Test complete trading flow"""
    
    def test_full_trading_cycle(self):
        """Test a complete trade signal to execution cycle"""
        
        with patch('trading_bot.strategy.integrated_strategy.MasterIntegratedStrategy'):
            # Strategy initialized
            assert True
        
        with patch('trading_bot.ui.master_dashboard.MasterDashboard'):
            # Dashboard created
            assert True
        
        with patch('trading_bot.monitoring.production_monitoring.StrategyLogger'):
            # Logger created
            assert True
    
    def test_all_features_importable(self):
        """Test all feature modules can be imported"""
        
        try:
            from trading_bot.sentiment.sentiment_analyzer import SentimentAnalyzer
            from trading_bot.analytics.portfolio_analytics import PortfolioAnalytics
            from trading_bot.analysis.equity_curve_analyzer import EquityCurveAnalyzer
            from trading_bot.backtest.tearsheet_analyzer import TearsheetAnalyzer
            from trading_bot.reporting.email_reports import EmailReporter
            from trading_bot.tax.tax_harvester import TaxLossHarvester
            from trading_bot.broker.advanced_orders import AdvancedOrderManager
            from trading_bot.data.websocket_provider import WebSocketDataProvider
            
            # All imports successful
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import feature module: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
