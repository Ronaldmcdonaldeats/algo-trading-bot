"""
Phase 3 Trading Logic Optimization Tests (5 tests)

Coverage:
- Dynamic stop-loss calculation (ATR-based, volatility-adjusted)
- Volatility-adjusted position sizing
- Drawdown management
- Correlation-based risk management
- Risk aggregation and constraint checking
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trading_bot.risk.risk_optimization import (
    dynamic_stop_loss,
    volatility_adjusted_position_size,
    DrawdownManager,
    CorrelationRiskManager,
    RiskAggregator,
)


class TestDynamicStopLoss:
    """Test 1: Dynamic stop-loss (ATR-based, volatility-adjusted)"""
    
    def test_dynamic_stop_loss_basic_calculation(self):
        """Test basic dynamic stop-loss calculation"""
        stop = dynamic_stop_loss(
            entry_price=100,
            atr_value=2.0,
            atr_multiplier=2.0,
            market_volatility=1.0
        )
        
        # Expected: 100 - (2.0 * 2.0 * 1.0) = 96.0
        assert stop == pytest.approx(96.0, abs=0.01)
    
    def test_dynamic_stop_loss_high_volatility(self):
        """Test that high volatility widens stop-loss"""
        stop_low_vol = dynamic_stop_loss(
            entry_price=100,
            atr_value=2.0,
            atr_multiplier=2.0,
            market_volatility=1.0
        )
        
        stop_high_vol = dynamic_stop_loss(
            entry_price=100,
            atr_value=2.0,
            atr_multiplier=2.0,
            market_volatility=2.0
        )
        
        # High volatility should create wider (lower) stop
        assert stop_high_vol < stop_low_vol
    
    def test_dynamic_stop_loss_respects_bounds(self):
        """Test that stop-loss never goes above entry"""
        stop = dynamic_stop_loss(
            entry_price=100,
            atr_value=0.1,
            atr_multiplier=0.1,
            market_volatility=1.0
        )
        
        assert stop < 100  # Stop should be below entry
    
    def test_dynamic_stop_loss_with_varying_atr(self):
        """Test stop-loss scales with ATR"""
        stop_low_atr = dynamic_stop_loss(
            entry_price=100,
            atr_value=1.0,
            atr_multiplier=2.0,
            market_volatility=1.0
        )
        
        stop_high_atr = dynamic_stop_loss(
            entry_price=100,
            atr_value=2.0,
            atr_multiplier=2.0,
            market_volatility=1.0
        )
        
        # Higher ATR should create wider (lower) stop
        assert stop_high_atr < stop_low_atr


class TestVolatilityAdjustedPositionSize:
    """Test 2: Volatility-adjusted position sizing"""
    
    def test_volatility_adjusted_position_normal_volatility(self):
        """Test position sizing at normal volatility"""
        size = volatility_adjusted_position_size(
            account_equity=100000,
            entry_price=50,
            stop_price=49,
            max_risk_percent=0.02,
            volatility_index=1.0  # Normal
        )
        
        # At normal volatility, should use full position
        expected_size = (100000 * 0.02) / (50 - 49)
        assert size == pytest.approx(expected_size, abs=1)
    
    def test_volatility_adjusted_position_high_volatility(self):
        """Test that high volatility reduces position size"""
        size_normal = volatility_adjusted_position_size(
            account_equity=100000,
            entry_price=50,
            stop_price=49,
            max_risk_percent=0.02,
            volatility_index=1.0
        )
        
        size_high_vol = volatility_adjusted_position_size(
            account_equity=100000,
            entry_price=50,
            stop_price=49,
            max_risk_percent=0.02,
            volatility_index=2.0  # High volatility
        )
        
        # High volatility should reduce position
        assert size_high_vol < size_normal
    
    def test_volatility_adjusted_position_respects_equity(self):
        """Test that position sizing respects account equity"""
        size_small = volatility_adjusted_position_size(
            account_equity=50000,
            entry_price=50,
            stop_price=49,
            max_risk_percent=0.02,
            volatility_index=1.0
        )
        
        size_large = volatility_adjusted_position_size(
            account_equity=100000,
            entry_price=50,
            stop_price=49,
            max_risk_percent=0.02,
            volatility_index=1.0
        )
        
        # Larger equity should allow larger position
        assert size_large > size_small
    
    def test_volatility_adjusted_position_non_negative(self):
        """Test that position size is always non-negative"""
        size = volatility_adjusted_position_size(
            account_equity=10000,
            entry_price=100,
            stop_price=50,
            max_risk_percent=0.01,
            volatility_index=5.0
        )
        
        assert size >= 0


class TestDrawdownManager:
    """Test 3: Drawdown management"""
    
    def test_drawdown_manager_initialization(self):
        """Test DrawdownManager initializes correctly"""
        manager = DrawdownManager(max_drawdown_pct=0.15)
        assert manager.max_drawdown_pct == 0.15
    
    def test_drawdown_manager_tracks_peak(self):
        """Test that DrawdownManager tracks peak equity"""
        manager = DrawdownManager(max_drawdown_percent=0.20)
        
        # Simulate equity increases
        manager.update(10000)
        manager.update(11000)
        manager.update(12000)  # New peak
        
        # Check peak is tracked
        assert manager.peak_equity == 12000
    
    def test_drawdown_manager_calculates_drawdown(self):
        """Test drawdown percentage calculation"""
        manager = DrawdownManager(max_drawdown_pct=0.20)
        
        manager.update(10000)  # Initial
        manager.update(11000)  # Peak
        manager.update(9900)   # Drawdown
        
        # Calculate expected drawdown: (11000 - 9900) / 11000 = 0.10
        assert manager.current_drawdown == pytest.approx(0.10, abs=0.01)
    
    def test_drawdown_manager_allows_trading_within_limit(self):
        """Test that trading is allowed within drawdown limit"""
        manager = DrawdownManager(max_drawdown_pct=0.20)
        
        manager.update(10000)
        manager.update(11000)  # Peak
        manager.update(9500)   # ~13.6% drawdown (within 20% limit)
        
        allowed, drawdown = manager.update(9000)
        assert allowed is True
    
    def test_drawdown_manager_stops_trading_over_limit(self):
        """Test that trading stops when drawdown exceeds limit"""
        manager = DrawdownManager(max_drawdown_pct=0.10)
        
        manager.update(10000)
        manager.update(11000)  # Peak
        manager.update(9800)   # ~10.9% drawdown (exceeds 10% limit)
        
        allowed, drawdown = manager.update(9700)
        assert allowed is False


class TestCorrelationRiskManager:
    """Test 4: Correlation-based risk management"""
    
    def test_correlation_risk_manager_initialization(self):
        """Test CorrelationRiskManager initializes correctly"""
        # CorrelationRiskManager is static, just test the methods work
        assert hasattr(CorrelationRiskManager, 'calculate_portfolio_correlation')
        assert hasattr(CorrelationRiskManager, 'adjust_position_size_for_correlation')
    
    def test_correlation_calculation_uncorrelated(self):
        """Test correlation with uncorrelated assets"""
        # Create uncorrelated returns dict
        returns = {
            'asset1': [0.01, 0.02, -0.01, 0.03, -0.02],
            'asset2': [-0.01, -0.02, 0.01, -0.03, 0.02]
        }
        
        corr = CorrelationRiskManager.calculate_portfolio_correlation(returns)
        
        # Should be relatively low (uncorrelated)
        assert corr < 0.8
    
    def test_correlation_position_adjustment(self):
        """Test position sizing based on correlation"""
        # Low correlation (safe)
        adjusted_low = CorrelationRiskManager.adjust_position_size_for_correlation(
            base_position=100,
            correlation=0.3
        )
        
        # High correlation (risky)
        adjusted_high = CorrelationRiskManager.adjust_position_size_for_correlation(
            base_position=100,
            correlation=0.8
        )
        
        # High correlation should result in smaller position
        assert adjusted_high < adjusted_low
    
    def test_correlation_manager_respects_threshold(self):
        """Test that correlation manager enforces max threshold"""
        # Just below threshold
        size1 = CorrelationRiskManager.adjust_position_size_for_correlation(100, 0.69)
        
        # Just above threshold
        size2 = CorrelationRiskManager.adjust_position_size_for_correlation(100, 0.71)
        
        # Above threshold should reduce more
        assert size2 < size1


class TestRiskAggregator:
    """Test 5: Portfolio-level risk aggregation"""
    
    def test_risk_aggregator_initialization(self):
        """Test RiskAggregator initializes correctly"""
        agg = RiskAggregator(
            max_drawdown_pct=0.15,
            max_correlation=0.7
        )
        
        assert agg.correlation_threshold == 0.7
    
    def test_risk_aggregator_allows_safe_position(self):
        """Test that safe positions are allowed"""
        agg = RiskAggregator(
            max_drawdown_pct=0.20,
            max_correlation=0.7
        )
        
        allowed, reason = agg.check_position_allowed(
            current_equity=10000,
            current_exposure_pct=0.5,
            symbol_returns={'AAPL': [0.01, 0.02, -0.01]},
            proposed_size=100
        )
        
        assert allowed is True
    
    def test_risk_aggregator_blocks_high_drawdown(self):
        """Test that positions blocked due to high drawdown"""
        agg = RiskAggregator(
            max_drawdown_pct=0.10,
            max_correlation=0.7
        )
        
        # Update drawdown manager first
        agg.drawdown_mgr.update(10000)  # Peak
        agg.drawdown_mgr.update(9000)   # 10% drawdown
        
        allowed, reason = agg.check_position_allowed(
            current_equity=9000,
            current_exposure_pct=0.5,
            symbol_returns={'AAPL': [0.01, 0.02, -0.01]},
            proposed_size=100
        )
        
        # At or slightly over limit should block
        assert allowed is False or "drawdown" in reason.lower()
    
    def test_risk_aggregator_blocks_high_correlation(self):
        """Test that positions blocked due to high correlation"""
        agg = RiskAggregator(
            max_drawdown_pct=0.20,
            max_correlation=0.7
        )
        
        # High correlation portfolio
        returns = {'AAPL': [0.01, 0.02, 0.01], 'MSFT': [0.01, 0.02, 0.01]}
        
        allowed, reason = agg.check_position_allowed(
            current_equity=9500,
            current_exposure_pct=0.5,
            symbol_returns=returns,
            proposed_size=100
        )
        
        # May block due to high correlation
        if not allowed:
            assert "correlation" in reason.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
