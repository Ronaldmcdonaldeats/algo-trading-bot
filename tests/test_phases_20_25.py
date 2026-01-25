"""
Test Suite for Phases 20-26
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from trading_bot.learn.momentum_scaling import MomentumScaler
from trading_bot.risk.options_hedging import OptionsHedger
from trading_bot.strategy.advanced_entry_filter import AdvancedEntryFilter
from trading_bot.analytics.realtime_metrics import MetricsCollector
from trading_bot.analytics.position_monitor import PositionMonitor
from trading_bot.risk.risk_adjusted_sizer import RiskAdjustedSizer
from trading_bot.strategy.multitimeframe_signals import MultiTimeframeSignalValidator
import pandas as pd
import numpy as np


def test_phase_20():
    """Test Phase 20: Momentum-Based Position Scaling"""
    print("\nTesting Phase 20: Momentum-Based Position Scaling")
    
    scaler = MomentumScaler()
    assert scaler is not None
    
    # Test with mock data (lowercase column names as numpy arrays)
    dates = pd.date_range('2024-01-01', periods=100)
    price_data = np.linspace(100, 110, 100) + np.random.normal(0, 1, 100)
    ohlcv = pd.DataFrame({
        'open': price_data.astype('float64'),
        'high': (price_data + 2).astype('float64'),
        'low': (price_data - 2).astype('float64'),
        'close': price_data.astype('float64'),
        'volume': np.ones(100, dtype='float64') * 1e6,
    }, index=dates)
    
    # Ensure columns exist and are properly typed
    assert 'close' in ohlcv.columns
    metrics = scaler.update_metrics('TEST', ohlcv)
    
    # If update_metrics returns None, try setting metrics directly
    if metrics is None:
        mult = scaler.get_scaling_multiplier('TEST')
    else:
        mult = scaler.get_scaling_multiplier('TEST')
    
    assert 0.5 <= mult <= 1.5
    print(f"[PASS] Phase 20: Momentum multiplier {mult:.2f}x")
    return True


def test_phase_21():
    """Test Phase 21: Options Hedging"""
    print("\nTesting Phase 21: Options Hedging")
    
    hedger = OptionsHedger()
    assert hedger is not None
    
    # Test hedge cost estimation
    estimate = hedger.estimate_hedge_cost(
        position_qty=100,
        position_price=100.0,
        volatility=0.25,
        hedge_type="protective_put",
    )
    
    assert estimate is not None
    assert hasattr(estimate, 'put_price')
    print(f"[PASS] Phase 21: Hedge put price ${estimate.put_price:.2f}")
    return True


def test_phase_22():
    """Test Phase 22: Advanced Entry Filtering"""
    print("\nTesting Phase 22: Advanced Entry Filtering")
    
    filter = AdvancedEntryFilter()
    assert filter is not None
    
    dates = pd.date_range('2024-01-01', periods=100)
    ohlcv = pd.DataFrame({
        'open': np.linspace(100, 110, 100),
        'high': np.linspace(105, 115, 100),
        'low': np.linspace(95, 105, 100),
        'close': np.linspace(102, 112, 100),
        'volume': np.ones(100) * 1e6,
    }, index=dates)
    
    validation = filter.validate_entry('TEST', ohlcv, signal=1)
    assert hasattr(validation, 'is_valid')
    assert hasattr(validation, 'confidence')
    print(f"[PASS] Phase 22: Entry validation confidence {validation.confidence:.2f}")
    return True


def test_phase_23():
    """Test Phase 23: Real-Time Metrics Monitor"""
    print("\nTesting Phase 23: Real-Time Metrics Monitor")
    
    from datetime import datetime
    collector = MetricsCollector()
    
    class MockPortfolio:
        def __init__(self):
            self.positions = {}
            self.cash = 50000
        def equity(self, prices):
            return 100000
    
    portfolio = MockPortfolio()
    prices = {'TEST': 100.0}
    equity_history = [100000, 101000, 102000]
    
    snapshot = collector.collect_metrics(
        ts=datetime.now(),
        iteration=1,
        portfolio=portfolio,
        prices=prices,
        equity_history=equity_history,
        trade_history=[],
        fills=[],
        rejections=[],
    )
    
    assert snapshot.equity == 100000
    print(f"[PASS] Phase 23: Metrics collected equity {snapshot.equity:,.0f}")
    return True


def test_phase_24():
    """Test Phase 24: Position Monitor"""
    print("\nTesting Phase 24: Position Monitor")
    
    from datetime import datetime
    monitor = PositionMonitor()
    
    monitor.add_position(
        symbol='TEST',
        entry_price=100.0,
        qty=100,
        entry_bar=0,
        ts=datetime.now(),
    )
    
    assert 'TEST' in monitor.positions
    
    alerts = monitor.update_position(
        symbol='TEST',
        current_price=101.0,
        momentum_score=0.7,
        iteration=10,
        ts=datetime.now(),
        take_profit=105.0,
        stop_loss=95.0,
        hedged=False,
    )
    
    assert isinstance(alerts, list)
    print(f"[PASS] Phase 24: Position tracking {len(alerts)} alerts")
    return True


def test_phase_25():
    """Test Phase 25: Risk-Adjusted Position Sizing"""
    print("\nTesting Phase 25: Risk-Adjusted Position Sizing")
    
    sizer = RiskAdjustedSizer()
    
    # Normal conditions
    sizer.update_state(
        current_equity=100000,
        consecutive_wins=0,
        total_trades=10,
        winning_trades=5,
        volatility=0.02,
    )
    
    mult = sizer.get_position_multiplier()
    assert 0.2 <= mult <= 2.0
    print(f"[PASS] Phase 25: Risk multiplier {mult:.2f}x")
    
    # Winning streak
    sizer.update_state(
        current_equity=100000,
        consecutive_wins=3,
        total_trades=3,
        winning_trades=3,
        volatility=0.02,
    )
    
    win_mult = sizer.get_position_multiplier()
    print(f"[PASS] Phase 25: Win streak multiplier {win_mult:.2f}x")
    return True


def test_phase_26():
    """Test Phase 26: Multi-Timeframe Signal Validation"""
    print("\nTesting Phase 26: Multi-Timeframe Signal Validation")
    
    validator = MultiTimeframeSignalValidator()
    
    # Add daily signal (bullish)
    validator.add_signal(
        symbol='TEST',
        signal=1,
        strength=0.8,
        price=100.0,
        timeframe="1d",
        indicators={'win_rate': 0.65}
    )
    
    # Add hourly signal (bullish, confirming)
    validator.add_signal(
        symbol='TEST',
        signal=1,
        strength=0.7,
        price=101.0,
        timeframe="1h",
        indicators={'win_rate': 0.60}
    )
    
    # Analyze
    analysis = validator.analyze('TEST')
    
    assert analysis.symbol == 'TEST'
    assert hasattr(analysis, 'is_confirmed')
    assert hasattr(analysis, 'alignment_strength')
    assert hasattr(analysis, 'expected_value')
    assert hasattr(analysis, 'recommendation')
    assert hasattr(analysis, 'confidence')
    
    print(f"[PASS] Phase 26: Signal confirmed={analysis.is_confirmed}, "
          f"confidence={analysis.confidence:.2f}, recommendation={analysis.recommendation}")
    return True


def main():
    print("=" * 60)
    print("Testing Phases 20-26: Advanced Trading Features")
    print("=" * 60)
    
    tests = [
        test_phase_20,
        test_phase_21,
        test_phase_22,
        test_phase_23,
        test_phase_24,
        test_phase_25,
        test_phase_26,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"[FAIL] {test.__name__}: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
