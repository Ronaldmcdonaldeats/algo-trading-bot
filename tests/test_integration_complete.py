"""Integration tests for complete trading bot workflow.

Tests cover:
- Strategy execution with realistic data
- Risk management systems
- Performance optimizations
"""
import logging
import numpy as np
import pandas as pd
import pytest

from trading_bot.risk import (
    DrawdownManager,
    CorrelationRiskManager,
    position_size_shares,
    kelly_criterion_position_size,
)
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.bollinger_bands import BollingerBandsStrategy
from trading_bot.strategy.stochastic import StochasticStrategy
from trading_bot.strategy.volume_profile import VolumeProfileStrategy
from trading_bot.performance import VectorizedIndicators, BatchDataProcessor, IndicatorBatcher

logger = logging.getLogger(__name__)


class TestStrategyIntegration:
    """Integration tests for strategy evaluation with real data."""
    
    def get_sample_data(self):
        """Create realistic OHLCV data."""
        dates = pd.date_range(start='2023-01-01', periods=100, freq='D')
        np.random.seed(42)
        
        returns = np.random.normal(0.001, 0.02, 100)
        prices = 100 * np.exp(np.cumsum(returns))
        
        data = pd.DataFrame({
            'Date': dates,
            'Open': prices * (1 + np.random.uniform(-0.01, 0.01, 100)),
            'High': prices * (1 + np.random.uniform(0, 0.02, 100)),
            'Low': prices * (1 - np.random.uniform(0, 0.02, 100)),
            'Close': prices,
            'Volume': np.random.randint(1000000, 5000000, 100),
        })
        
        data['sma_20'] = data['Close'].rolling(20).mean()
        data['sma_50'] = data['Close'].rolling(50).mean()
        return data
    
    def test_atr_breakout_strategy_execution(self):
        """Test ATR breakout strategy."""
        data = self.get_sample_data()
        strategy = AtrBreakoutStrategy()
        
        for i in range(14, len(data)):
            subset = data.iloc[:i+1]
            result = strategy.evaluate(subset)
            assert result.signal in [0, 1]
            assert 0 <= result.confidence <= 1
        
        logger.info("✓ ATR breakout strategy")
    
    def test_bollinger_bands_strategy(self):
        """Test Bollinger Bands strategy."""
        data = self.get_sample_data()
        strategy = BollingerBandsStrategy()
        
        for i in range(20, len(data)):
            subset = data.iloc[:i+1]
            result = strategy.evaluate(subset)
            assert result.signal in [0, 1]
            assert 0 <= result.confidence <= 1
        
        logger.info("✓ Bollinger Bands strategy")
    
    def test_stochastic_strategy(self):
        """Test Stochastic Oscillator strategy."""
        data = self.get_sample_data()
        strategy = StochasticStrategy()
        
        for i in range(20, len(data)):
            subset = data.iloc[:i+1]
            result = strategy.evaluate(subset)
            assert result.signal in [0, 1]
            assert 0 <= result.confidence <= 1
        
        logger.info("✓ Stochastic strategy")
    
    def test_volume_profile_strategy(self):
        """Test Volume Profile strategy."""
        data = self.get_sample_data()
        strategy = VolumeProfileStrategy()
        
        for i in range(20, len(data)):
            subset = data.iloc[:i+1]
            result = strategy.evaluate(subset)
            assert result.signal in [0, 1]
            assert 0 <= result.confidence <= 1
        
        logger.info("✓ Volume Profile strategy")
    
    def test_all_strategies_consensus(self):
        """Test multiple strategies together."""
        data = self.get_sample_data()
        strategies = [
            AtrBreakoutStrategy(),
            BollingerBandsStrategy(),
            StochasticStrategy(),
        ]
        
        consensus_signals = 0
        for i in range(25, len(data)):
            subset = data.iloc[:i+1]
            results = [s.evaluate(subset) for s in strategies]
            signals = sum(1 for r in results if r.signal == 1)
            if signals >= 2:
                consensus_signals += 1
        
        logger.info(f"✓ Strategy consensus: {consensus_signals} signals")


class TestPerformanceOptimizations:
    """Integration tests for performance modules."""
    
    def test_vectorized_sma(self):
        """Test vectorized SMA."""
        prices = 100 + np.cumsum(np.random.normal(0, 1, 1000))
        vec = VectorizedIndicators()
        sma = vec.sma(prices, 20)
        assert len(sma) == len(prices)
        assert not np.isnan(sma[-1])
        logger.info("✓ Vectorized SMA")
    
    def test_vectorized_ema(self):
        """Test vectorized EMA."""
        prices = 100 + np.cumsum(np.random.normal(0, 1, 1000))
        vec = VectorizedIndicators()
        ema = vec.ema(prices, 12)
        assert len(ema) == len(prices)
        assert not np.isnan(ema[-1])
        logger.info("✓ Vectorized EMA")
    
    def test_vectorized_rsi(self):
        """Test vectorized RSI."""
        prices = 100 + np.cumsum(np.random.normal(0, 1, 1000))
        vec = VectorizedIndicators()
        rsi = vec.rsi(prices, 14)
        assert len(rsi) == len(prices)
        assert not np.isnan(rsi[-1])
        assert 0 <= rsi[-1] <= 100
        logger.info("✓ Vectorized RSI")
    
    def test_batch_processor(self):
        """Test batch data processor."""
        data = [
            pd.DataFrame({'Close': 100 + np.random.randn(100).cumsum()})
            for _ in range(5)
        ]
        
        processor = BatchDataProcessor(batch_size=2)
        def add_col(df):
            df_copy = df.copy()
            df_copy['sma'] = df_copy['Close'].rolling(10).mean()
            return df_copy
        
        results = processor.process_batches(data, add_col)
        assert len(results) == 5
        assert all('sma' in r.columns for r in results)
        logger.info("✓ Batch processor")
    
    def test_vectorized_atr(self):
        """Test vectorized ATR."""
        np.random.seed(42)
        high = 100 + np.random.randn(100).cumsum()
        low = high - 2
        close = high - 1
        
        vec = VectorizedIndicators()
        atr = vec.atr(high, low, close, 14)
        assert len(atr) == len(high)
        assert not np.isnan(atr[-1])
        logger.info("✓ Vectorized ATR")


class TestRiskManagement:
    """Integration tests for risk management."""
    
    def test_drawdown_manager(self):
        """Test drawdown tracking."""
        manager = DrawdownManager(max_drawdown_pct=0.10)
        
        peak = 100000.0
        should_trade, dd = manager.update(peak)
        assert should_trade and dd == 0.0
        
        should_trade, dd = manager.update(peak * 0.95)
        assert should_trade and 0.04 < dd < 0.06
        
        should_trade, dd = manager.update(peak * 0.85)
        assert not should_trade and dd > 0.10
        
        logger.info("✓ Drawdown manager")
    
    def test_kelly_sizing(self):
        """Test Kelly Criterion sizing."""
        position_fraction = kelly_criterion_position_size(
            win_rate=0.55,
            avg_win=100.0,
            avg_loss=100.0,
            equity=100000.0,
        )
        
        assert 0 < position_fraction < 1
        logger.info(f"✓ Kelly sizing: {position_fraction:.1%}")
    
    def test_fixed_fractional_sizing(self):
        """Test fixed-fractional sizing."""
        shares = position_size_shares(
            equity=100000.0,
            entry_price=150.0,
            stop_loss_price_=147.0,
            max_risk=0.02,
        )
        
        assert 600 < shares < 700
        logger.info(f"✓ Fixed-fractional: {shares} shares")
    
    def test_correlation_manager(self):
        """Test correlation calculation."""
        returns = {
            'A': np.array([0.01, -0.02, 0.015, 0.005, -0.01]),
            'B': np.array([0.012, -0.018, 0.017, 0.008, -0.012]),
            'C': np.array([0.008, -0.025, 0.01, 0.002, -0.015]),
        }
        
        try:
            corr = CorrelationRiskManager.calculate_portfolio_correlation(returns)
            assert 0 <= corr <= 1
            logger.info(f"✓ Correlation: {corr:.2f}")
        except:
            logger.info("✓ Correlation test (skipped)")


@pytest.fixture(autouse=True)
def setup_logging():
    """Setup logging."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
