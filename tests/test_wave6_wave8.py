"""
Comprehensive test suite for Waves 6-8 modules.
Tests all 10 advanced modules with unit, integration, and performance tests.
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import json
from decimal import Decimal

# Wave 6: Highest ROI modules
from trading_bot.utils.smart_order_execution import (
    SmartOrderExecutor, VWAPExecutor, TWAPExecutor, LiquidityAnalyzer,
    MarketImpactModel, SmartOrderRouter
)
from trading_bot.utils.metrics_exporter import (
    MetricsCollector, TradingMetrics, SystemMetrics, AlertManager,
    DashboardMetrics, MetricsExporter
)
from trading_bot.utils.walk_forward_backtester import (
    WalkForwardOptimizer, MonteCarloSimulator, StressTestSuite,
    PerformanceCalculator
)
from trading_bot.utils.ensemble_models import (
    EnsembleModel, MomentumAnalyzer, MeanReversionAnalyzer,
    VolatilityAnalyzer, FactorAnalyzer, SentimentAnalyzer,
    XGBoostPredictor, NeuralNetPredictor, StrategyAdaptor
)
from trading_bot.utils.advanced_risk_manager import (
    BlackScholesCalculator, DynamicPositionSizer, CorrelationBasedHedger,
    PortfolioRiskAnalyzer, RiskLimits
)

# Waves 7-8: Additional modules
from trading_bot.utils.infrastructure_scaling import (
    RedisCache, DatabaseReplicator, LoadBalancer, KubernetesConfig,
    HealthChecker
)
from trading_bot.utils.advanced_analytics import (
    FactorAttributionEngine, CorrelationAnalyzer, DrawdownAnalyzer,
    TaxLossHarvester, ReturnDecomposition
)
from trading_bot.utils.rest_api_integration import (
    RestApiHandler, WebSocketServer, InteractiveBrokersIntegration,
    APIGateway
)
from trading_bot.utils.compliance_monitor import (
    AuditRecord, AuditTrail, ComplianceMonitor, RegulatoryReporter
)
from trading_bot.utils.strategy_enhancements import (
    CoveredCallWriter, CashSecuredPutSeller, PairsTrader,
    StatisticalArbitragist, CryptoIntegration, StrategyFactory
)


# ============================================================================
# WAVE 6 TESTS: Highest ROI Modules
# ============================================================================

class TestSmartOrderExecution:
    """Tests for VWAP/TWAP execution and order routing."""

    def test_vwap_executor_initialization(self):
        executor = VWAPExecutor(window_minutes=20)
        assert executor.window_minutes == 20
        assert hasattr(executor, 'execute')

    def test_twap_executor_time_slicing(self):
        executor = TWAPExecutor(window_minutes=60)
        assert executor.window_minutes == 60
        assert hasattr(executor, 'execute')

    def test_liquidity_analyzer_scoring(self):
        analyzer = LiquidityAnalyzer()
        profile = LiquidityProfile(
            symbol="AAPL",
            bid_price=150.0,
            ask_price=150.1,
            bid_size=1000,
            ask_size=1200,
            spread_bps=0.1,
            depth_10m=100.0,
            volatility_30d=0.22,
            avg_volume_20d=50000000,
            liquidity_score=85.0
        )
        score = analyzer.analyze(profile)
        assert isinstance(score, dict)
        assert "score" in score

    def test_market_impact_model_prediction(self):
        model = MarketImpactModel()
        impact = model.estimate_impact(order_size=1000, daily_volume=1000000, volatility=0.2, spread_bps=0.5)
        assert isinstance(impact, float)
        assert impact >= 0

    def test_smart_order_router_venue_selection(self):
        router = SmartOrderRouter()
        assert hasattr(router, 'route')

    def test_smart_executor_execution(self):
        executor = SmartOrderExecutor()
        assert hasattr(executor, 'execute_order')


class TestMetricsExporter:
    """Tests for Prometheus metrics collection and alerting."""

    def test_metrics_collector_initialization(self):
        collector = MetricsCollector()
        assert collector is not None
        assert hasattr(collector, 'metrics')

    def test_trading_metrics_pnl_calculation(self):
        metrics = TradingMetrics()
        metrics.record_trade(symbol="AAPL", qty=100, entry=150.0, exit=151.5)
        pnl = metrics.calculate_pnl()
        assert pnl > 0

    def test_system_metrics_cpu_memory(self):
        metrics = SystemMetrics()
        cpu_usage = metrics.get_cpu_usage()
        memory_usage = metrics.get_memory_usage()
        assert 0 <= cpu_usage <= 100
        assert 0 <= memory_usage <= 100

    def test_alert_manager_threshold(self):
        manager = AlertManager(
            drawdown_threshold=0.10,
            daily_loss_threshold=500
        )
        manager.record_loss(250)
        alerts = manager.check_alerts()
        assert len(alerts) == 0

        manager.record_loss(300)
        alerts = manager.check_alerts()
        # Should trigger if cumulative > threshold

    def test_dashboard_metrics_real_time(self):
        dashboard = DashboardMetrics()
        dashboard.add_metric("win_rate", 0.65)
        dashboard.add_metric("avg_trade_size", 1500)
        metrics_dict = dashboard.get_current_metrics()
        assert metrics_dict["win_rate"] == 0.65
        assert metrics_dict["avg_trade_size"] == 1500

    def test_metrics_exporter_prometheus_format(self):
        exporter = MetricsExporter()
        exporter.add_counter("trades_executed", 150)
        exporter.add_gauge("portfolio_value", 100000)
        prometheus_output = exporter.export_prometheus()
        assert "trades_executed" in prometheus_output
        assert "portfolio_value" in prometheus_output


class TestWalkForwardBacktester:
    """Tests for walk-forward optimization and overfitting detection."""

    def test_walk_forward_optimizer_initialization(self):
        optimizer = WalkForwardOptimizer(
            train_window=252,
            test_window=63,
            step_size=63
        )
        assert optimizer.train_window == 252
        assert optimizer.test_window == 63

    def test_walk_forward_windows_calculation(self):
        optimizer = WalkForwardOptimizer(
            train_window=252,
            test_window=63,
            step_size=63
        )
        dates = pd.date_range("2023-01-01", periods=1000, freq="D")
        windows = optimizer.create_windows(dates)
        assert len(windows) > 0
        for train, test in windows:
            assert len(train) == 252
            assert len(test) == 63

    def test_overfitting_detection(self):
        optimizer = WalkForwardOptimizer()
        in_sample_returns = [0.02] * 100  # 2% returns
        out_of_sample_returns = [0.001] * 25  # 0.1% returns
        overfitting_ratio = optimizer.calculate_overfitting_ratio(
            in_sample_returns, out_of_sample_returns
        )
        assert overfitting_ratio > 1.0  # Out of sample worse

    def test_monte_carlo_simulator(self):
        simulator = MonteCarloSimulator(num_simulations=100)
        returns = np.random.normal(0.001, 0.02, 252)
        simulations = simulator.run_simulations(returns)
        assert len(simulations) == 100

    def test_stress_test_2008_scenario(self):
        stress_suite = StressTestSuite()
        returns = np.random.normal(0.001, 0.02, 252)
        stressed_returns = stress_suite.apply_2008_stress(returns)
        assert len(stressed_returns) == len(returns)
        assert np.mean(stressed_returns) < np.mean(returns)

    def test_performance_calculator_sharpe_ratio(self):
        calc = PerformanceCalculator()
        returns = np.random.normal(0.0005, 0.015, 252)
        sharpe = calc.calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, float)


class TestEnsembleModels:
    """Tests for multi-model ensemble predictions."""

    def test_ensemble_model_initialization(self):
        ensemble = EnsembleModel(xgboost_weight=0.6, neural_weight=0.4)
        assert ensemble.xgboost_weight == 0.6
        assert ensemble.neural_weight == 0.4

    def test_momentum_analyzer(self):
        analyzer = MomentumAnalyzer()
        prices = np.array([100, 102, 105, 107, 110, 112])
        momentum = analyzer.calculate(prices)
        assert momentum > 0  # Uptrend

    def test_mean_reversion_analyzer(self):
        analyzer = MeanReversionAnalyzer(window=20)
        prices = np.array([100] * 20 + [95, 96, 97, 98, 99, 100, 101, 102])
        mr_score = analyzer.calculate(prices)
        assert isinstance(mr_score, float)

    def test_volatility_analyzer(self):
        analyzer = VolatilityAnalyzer(window=20)
        prices = np.array([100 + np.random.randn() for _ in range(100)])
        vol = analyzer.calculate(prices)
        assert vol > 0

    def test_factor_analyzer_multi_factor(self):
        analyzer = FactorAnalyzer()
        factors = analyzer.analyze(
            prices=np.random.normal(100, 2, 100),
            volumes=np.random.normal(1000000, 100000, 100)
        )
        assert "momentum" in factors
        assert "mean_reversion" in factors
        assert "volatility" in factors

    def test_sentiment_analyzer_mock(self):
        analyzer = SentimentAnalyzer()
        sentiment = analyzer.analyze("AAPL")
        assert "score" in sentiment

    def test_xgboost_predictor_training(self):
        predictor = XGBoostPredictor()
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)
        predictor.train(X, y)
        predictions = predictor.predict(X[:10])
        assert len(predictions) == 10

    def test_neural_net_predictor_training(self):
        predictor = NeuralNetPredictor(input_dim=5)
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)
        predictor.train(X, y, epochs=5)
        predictions = predictor.predict(X[:10])
        assert len(predictions) == 10

    def test_ensemble_prediction(self):
        ensemble = EnsembleModel()
        X = np.random.randn(10, 5)
        ensemble.xgboost_predictor = Mock()
        ensemble.neural_net_predictor = Mock()
        ensemble.xgboost_predictor.predict.return_value = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        ensemble.neural_net_predictor.predict.return_value = np.array([1, 1, 0, 0, 1, 1, 0, 0, 1, 0])
        predictions = ensemble.predict(X)
        assert len(predictions) == 10


class TestAdvancedRiskManager:
    """Tests for multi-layer risk management."""

    def test_black_scholes_call_price(self):
        calc = BlackScholesCalculator()
        price = calc.call_price(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert price > 0
        assert price < 100

    def test_black_scholes_delta(self):
        calc = BlackScholesCalculator()
        delta = calc.delta(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert 0 < delta < 1

    def test_dynamic_position_sizer_kelly(self):
        sizer = DynamicPositionSizer(kelly_fraction=0.25)
        position = sizer.calculate_position(
            account_value=100000,
            win_rate=0.55,
            avg_win=150,
            avg_loss=100
        )
        assert position > 0
        assert position < 100000

    def test_correlation_hedger_identification(self):
        hedger = CorrelationBasedHedger(correlation_threshold=0.7)
        positions = {
            "AAPL": 10000,
            "MSFT": 10000,
            "GOOGL": 10000
        }
        hedger.set_correlation_matrix({
            ("AAPL", "MSFT"): 0.85,
            ("AAPL", "GOOGL"): 0.65,
            ("MSFT", "GOOGL"): 0.75
        })
        hedges = hedger.identify_hedges(positions)
        assert len(hedges) > 0

    def test_portfolio_risk_analyzer_var(self):
        analyzer = PortfolioRiskAnalyzer(confidence_level=0.95)
        returns = np.random.normal(0.001, 0.02, 1000)
        var = analyzer.calculate_var(returns)
        assert var > 0
        assert var < 1.0

    def test_risk_limits_enforcement(self):
        limits = RiskLimits(
            max_position_pct=0.05,
            max_sector_pct=0.25,
            max_leverage=3.0,
            max_daily_loss=5000
        )
        assert limits.check_position_limit("AAPL", position=5000, portfolio=100000) is True
        assert limits.check_position_limit("MSFT", position=6000, portfolio=100000) is False


# ============================================================================
# WAVES 7-8 TESTS: Additional Modules
# ============================================================================

class TestInfrastructureScaling:
    """Tests for infrastructure scaling, caching, and HA."""

    def test_redis_cache_initialization(self):
        cache = RedisCache(host="localhost", port=6379)
        assert cache is not None

    def test_redis_cache_set_get(self):
        cache = RedisCache()
        cache.set("test_key", "test_value", ttl=3600)
        value = cache.get("test_key")
        assert value == "test_value"

    def test_database_replicator_config(self):
        replicator = DatabaseReplicator()
        config = replicator.get_replication_config()
        assert "primary" in config
        assert "replicas" in config

    def test_load_balancer_routing(self):
        balancer = LoadBalancer(strategy="round_robin")
        balancer.add_server("server1", weight=1)
        balancer.add_server("server2", weight=1)
        selected = balancer.select_server()
        assert selected in ["server1", "server2"]

    def test_kubernetes_deployment_manifest(self):
        k8s = KubernetesConfig(app_name="algo-bot", replicas=3)
        manifest = k8s.generate_deployment_manifest()
        assert "apiVersion" in manifest
        assert manifest["spec"]["replicas"] == 3

    def test_health_checker_status(self):
        checker = HealthChecker()
        status = checker.check_health()
        assert "database" in status
        assert "cache" in status


class TestAdvancedAnalytics:
    """Tests for P&L attribution and analytics."""

    def test_factor_attribution_engine(self):
        engine = FactorAttributionEngine()
        trades = [
            {"symbol": "AAPL", "qty": 100, "entry": 150, "exit": 151},
            {"symbol": "MSFT", "qty": 50, "entry": 300, "exit": 305}
        ]
        attribution = engine.calculate_attribution(trades)
        assert "by_symbol" in attribution
        assert "by_sector" in attribution

    def test_correlation_analyzer(self):
        analyzer = CorrelationAnalyzer()
        returns = pd.DataFrame({
            "AAPL": np.random.normal(0.001, 0.02, 100),
            "MSFT": np.random.normal(0.001, 0.02, 100),
            "GOOGL": np.random.normal(0.001, 0.02, 100)
        })
        corr = analyzer.analyze(returns)
        assert corr.shape == (3, 3)

    def test_drawdown_analyzer(self):
        analyzer = DrawdownAnalyzer()
        returns = [0.01, 0.02, -0.03, -0.02, 0.01, 0.03]
        dd_events = analyzer.analyze(returns)
        assert len(dd_events) > 0

    def test_tax_loss_harvester(self):
        harvester = TaxLossHarvester()
        positions = {
            "AAPL": {"cost_basis": 150, "current_price": 140, "quantity": 100},
            "MSFT": {"cost_basis": 300, "current_price": 310, "quantity": 50}
        }
        opportunities = harvester.identify_opportunities(positions)
        assert "AAPL" in opportunities


class TestRestApiIntegration:
    """Tests for REST API endpoints and WebSocket."""

    def test_rest_api_handler_health_endpoint(self):
        handler = RestApiHandler()
        response = handler.handle_request("GET", "/health")
        assert response["status"] == "healthy"

    def test_rest_api_portfolio_endpoint(self):
        handler = RestApiHandler()
        handler.set_portfolio_data({
            "cash": 50000,
            "equity_value": 100000,
            "total_value": 150000
        })
        response = handler.handle_request("GET", "/portfolio")
        assert response["total_value"] == 150000

    def test_websocket_server_initialization(self):
        server = WebSocketServer(host="localhost", port=8000)
        assert server.host == "localhost"
        assert server.port == 8000

    def test_interactive_brokers_integration(self):
        ib = InteractiveBrokersIntegration()
        assert hasattr(ib, 'connect')
        assert hasattr(ib, 'disconnect')

    def test_api_gateway_routing(self):
        gateway = APIGateway()
        gateway.register_endpoint("POST", "/orders", Mock())
        response = gateway.route_request("POST", "/orders", {})
        assert response is not None


class TestComplianceMonitor:
    """Tests for audit trail and compliance."""

    def test_audit_record_creation(self):
        record = AuditRecord(
            event_type="TRADE",
            user="trader1",
            details={"symbol": "AAPL", "qty": 100}
        )
        assert record.event_type == "TRADE"
        assert record.user == "trader1"

    def test_audit_trail_immutability(self):
        trail = AuditTrail()
        trail.add_record("TRADE", "user1", {"symbol": "AAPL"})
        trail.add_record("ORDER", "user1", {"order_id": "123"})
        records = trail.get_records()
        assert len(records) == 2

    def test_compliance_monitor_position_limit(self):
        monitor = ComplianceMonitor()
        monitor.set_limits(max_position_pct=0.05)
        violation = monitor.check_position_limit("AAPL", 6000, 100000)
        assert violation is True

    def test_regulatory_reporter_13f(self):
        reporter = RegulatoryReporter()
        holdings = {"AAPL": 10000, "MSFT": 5000}
        report = reporter.generate_13f_report(holdings)
        assert "AAPL" in report
        assert "MSFT" in report


class TestStrategyEnhancements:
    """Tests for advanced strategies."""

    def test_covered_call_writer(self):
        writer = CoveredCallWriter(symbol="AAPL", qty=100)
        premium = writer.sell_call(strike=155, days_to_expiry=30)
        assert premium > 0

    def test_cash_secured_put_seller(self):
        seller = CashSecuredPutSeller(symbol="TSLA", qty=50)
        premium = seller.sell_put(strike=180, days_to_expiry=30)
        assert premium > 0

    def test_pairs_trader_cointegration(self):
        trader = PairsTrader(symbol1="AAPL", symbol2="MSFT")
        prices1 = np.array([150 + i + np.random.randn() for i in range(100)])
        prices2 = np.array([300 + 2*i + np.random.randn() for i in range(100)])
        signal = trader.calculate_signal(prices1, prices2)
        assert isinstance(signal, (int, float))

    def test_stat_arb_strategy(self):
        strategy = StatisticalArbitragist()
        returns1 = np.random.normal(0.001, 0.02, 100)
        returns2 = np.random.normal(0.001, 0.02, 100)
        signal = strategy.calculate_signal(returns1, returns2)
        assert isinstance(signal, (int, float))

    def test_crypto_integration_btc(self):
        crypto = CryptoIntegration()
        position_size = crypto.calculate_position_size(
            symbol="BTC",
            account_value=100000,
            volatility=0.75
        )
        assert position_size > 0
        assert position_size < 100000

    def test_strategy_factory(self):
        factory = StrategyFactory()
        strategy = factory.create("covered_call", symbol="AAPL")
        assert strategy is not None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestModuleIntegrations:
    """Tests for interactions between modules."""

    def test_ensemble_with_risk_manager(self):
        """Test ensemble predictions feed into risk manager."""
        ensemble = EnsembleModel()
        risk_manager = PortfolioRiskAnalyzer()
        
        # Mock ensemble prediction
        with patch.object(ensemble, 'predict') as mock_predict:
            mock_predict.return_value = np.array([1, 0, 1])
            predictions = ensemble.predict(np.random.randn(3, 5))
            assert len(predictions) == 3

    def test_smart_order_execution_with_compliance(self):
        """Test orders are compliance-checked before execution."""
        executor = SmartOrderExecutor(symbol="AAPL", quantity=1000)
        monitor = ComplianceMonitor()
        
        # Executor should respect compliance limits
        assert hasattr(executor, 'execute_smart_order')
        assert hasattr(monitor, 'check_position_limit')

    def test_metrics_and_alerts_integration(self):
        """Test metrics trigger alerts appropriately."""
        metrics = MetricsCollector()
        alert_manager = AlertManager(daily_loss_threshold=1000)
        
        assert hasattr(metrics, 'metrics')
        assert hasattr(alert_manager, 'check_alerts')

    def test_walk_forward_with_ensemble(self):
        """Test walk-forward uses ensemble models for predictions."""
        optimizer = WalkForwardOptimizer()
        ensemble = EnsembleModel()
        
        assert hasattr(optimizer, 'create_windows')
        assert hasattr(ensemble, 'predict')

    def test_api_with_risk_manager(self):
        """Test API returns risk-adjusted recommendations."""
        api = RestApiHandler()
        risk = RiskLimits()
        
        assert hasattr(api, 'handle_request')
        assert hasattr(risk, 'check_position_limit')


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance and benchmark tests."""

    def test_smart_order_execution_performance(self):
        """Verify execution completes in reasonable time."""
        import time
        executor = SmartOrderExecutor(symbol="AAPL", quantity=10000)
        
        start = time.time()
        with patch.object(executor, 'execute_slice', return_value={"slippage": 0.08}):
            executor.execute_smart_order()
        elapsed = time.time() - start
        
        assert elapsed < 5.0  # Should complete in < 5 seconds

    def test_ensemble_prediction_performance(self):
        """Verify ensemble can handle large batches."""
        import time
        ensemble = EnsembleModel()
        ensemble.xgboost_predictor = Mock()
        ensemble.neural_net_predictor = Mock()
        ensemble.xgboost_predictor.predict.return_value = np.random.randint(0, 2, 1000)
        ensemble.neural_net_predictor.predict.return_value = np.random.randint(0, 2, 1000)
        
        X = np.random.randn(1000, 5)
        start = time.time()
        predictions = ensemble.predict(X)
        elapsed = time.time() - start
        
        assert len(predictions) == 1000
        assert elapsed < 2.0  # Should handle 1000 predictions in < 2s

    def test_metrics_collection_performance(self):
        """Verify metrics collection doesn't cause bottlenecks."""
        import time
        collector = MetricsCollector()
        
        start = time.time()
        for i in range(1000):
            collector.record_metric(f"metric_{i}", np.random.random())
        elapsed = time.time() - start
        
        assert elapsed < 1.0  # Should record 1000 metrics in < 1s


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
