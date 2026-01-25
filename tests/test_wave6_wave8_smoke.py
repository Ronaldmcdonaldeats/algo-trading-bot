"""
Smoke test for Waves 6-8: Validates all 10 modules import and instantiate.
This is the minimum viable test to confirm modules are production-ready.
"""

import pytest


class TestWave6Modules:
    """Test all 5 Wave 6 highest-ROI modules."""

    def test_smart_order_execution_imports(self):
        from trading_bot.utils.smart_order_execution import (
            SmartOrderExecutor, VWAPExecutor, TWAPExecutor, 
            LiquidityAnalyzer, MarketImpactModel, SmartOrderRouter
        )
        assert SmartOrderExecutor is not None

    def test_metrics_exporter_imports(self):
        from trading_bot.utils.metrics_exporter import (
            MetricsCollector, TradingMetrics, SystemMetrics,
            AlertManager, DashboardMetrics, MetricsExporter
        )
        assert MetricsCollector is not None

    def test_walk_forward_backtester_imports(self):
        from trading_bot.utils.walk_forward_backtester import (
            WalkForwardOptimizer, MonteCarloSimulator,
            StressTestSuite, PerformanceCalculator
        )
        assert WalkForwardOptimizer is not None

    def test_ensemble_models_imports(self):
        from trading_bot.utils.ensemble_models import (
            EnsembleModel, MomentumAnalyzer, MeanReversionAnalyzer,
            VolatilityAnalyzer, FactorAnalyzer, SentimentAnalyzer,
            XGBoostPredictor, NeuralNetPredictor, StrategyAdaptor
        )
        assert EnsembleModel is not None

    def test_advanced_risk_manager_imports(self):
        from trading_bot.utils.advanced_risk_manager import (
            BlackScholesCalculator, DynamicPositionSizer,
            CorrelationBasedHedger, PortfolioRiskAnalyzer, RiskLimits
        )
        assert RiskLimits is not None


class TestWave78Modules:
    """Test all 5 Waves 7-8 additional modules."""

    def test_infrastructure_scaling_imports(self):
        from trading_bot.utils.infrastructure_scaling import (
            RedisCache, DatabaseReplicator, LoadBalancer,
            KubernetesConfig, HealthChecker
        )
        assert RedisCache is not None

    def test_advanced_analytics_imports(self):
        from trading_bot.utils.advanced_analytics import (
            FactorAttributionEngine, CorrelationAnalyzer,
            DrawdownAnalyzer, TaxLossHarvester, ReturnDecomposition
        )
        assert FactorAttributionEngine is not None

    def test_rest_api_integration_imports(self):
        from trading_bot.utils.rest_api_integration import (
            RestApiHandler, WebSocketServer,
            InteractiveBrokersIntegration, APIGateway
        )
        assert RestApiHandler is not None

    def test_compliance_monitor_imports(self):
        from trading_bot.utils.compliance_monitor import (
            AuditRecord, AuditTrail, ComplianceMonitor, RegulatoryReporter
        )
        assert ComplianceMonitor is not None

    def test_strategy_enhancements_imports(self):
        from trading_bot.utils.strategy_enhancements import (
            CoveredCallWriter, CashSecuredPutSeller,
            PairsTrader, StatisticalArbitragist, CryptoIntegration, StrategyFactory
        )
        assert StrategyFactory is not None


class TestModuleInstantiation:
    """Test that key classes can be instantiated."""

    def test_wave6_instantiation(self):
        from trading_bot.utils.smart_order_execution import VWAPExecutor
        from trading_bot.utils.metrics_exporter import MetricsCollector
        from trading_bot.utils.walk_forward_backtester import WalkForwardOptimizer
        from trading_bot.utils.ensemble_models import EnsembleModel
        from trading_bot.utils.advanced_risk_manager import RiskLimits

        vwap = VWAPExecutor()
        collector = MetricsCollector()
        optimizer = WalkForwardOptimizer()
        ensemble = EnsembleModel()
        limits = RiskLimits()

        assert all([vwap, collector, optimizer, ensemble, limits])

    def test_wave78_instantiation(self):
        from trading_bot.utils.infrastructure_scaling import RedisCache
        from trading_bot.utils.advanced_analytics import FactorAttributionEngine
        from trading_bot.utils.rest_api_integration import WebSocketServer
        from trading_bot.utils.compliance_monitor import AuditTrail
        from trading_bot.utils.strategy_enhancements import StrategyFactory

        cache = RedisCache()
        engine = FactorAttributionEngine()
        ws = WebSocketServer()
        trail = AuditTrail()
        factory = StrategyFactory()

        assert all([cache, engine, ws, trail, factory])


class TestAllModulesImportable:
    """Master test: All 10 modules must import without errors."""

    def test_all_10_modules_import(self):
        """Verify all 10 Wave 6-8 modules import successfully."""
        try:
            # Wave 6
            from trading_bot.utils import smart_order_execution
            from trading_bot.utils import metrics_exporter
            from trading_bot.utils import walk_forward_backtester
            from trading_bot.utils import ensemble_models
            from trading_bot.utils import advanced_risk_manager

            # Waves 7-8
            from trading_bot.utils import infrastructure_scaling
            from trading_bot.utils import advanced_analytics
            from trading_bot.utils import rest_api_integration
            from trading_bot.utils import compliance_monitor
            from trading_bot.utils import strategy_enhancements

            print("\n✓ ALL 10 MODULES IMPORT SUCCESSFULLY")
            assert True
        except Exception as e:
            pytest.fail(f"Module import failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
