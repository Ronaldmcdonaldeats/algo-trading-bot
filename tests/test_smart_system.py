"""Comprehensive tests for smart trading system modules."""

import pytest
import os
import shutil
import tempfile
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Import modules to test
from src.trading_bot.data.batch_downloader import BatchDownloader
from src.trading_bot.data.smart_selector import StockScorer, StockScore
from src.trading_bot.data.performance_tracker import PerformanceTracker
from src.trading_bot.data.portfolio_optimizer import PortfolioOptimizer
from src.trading_bot.data.risk_manager import RiskManager
from src.trading_bot.data.ml_predictor import MLPredictor


class TestBatchDownloader:
    """Tests for batch data downloading."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = BatchDownloader(cache_dir=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_key_generation(self):
        """Test cache key format."""
        key = self.downloader._cache_key('AAPL', '1mo', '1d')
        assert key == 'AAPL_1mo_1d'
    
    def test_cache_path_generation(self):
        """Test cache file path."""
        path = self.downloader._cache_path('AAPL', '1mo', '1d')
        assert path.endswith('.parquet')
        assert 'AAPL' in path
    
    def test_save_and_load_cache(self):
        """Test caching mechanism."""
        df = pd.DataFrame({
            'Open': [100, 101, 102],
            'High': [101, 102, 103],
            'Low': [99, 100, 101],
            'Close': [100.5, 101.5, 102.5],
            'Volume': [1000000, 1100000, 900000],
        })
        
        self.downloader._save_cache('AAPL', '1mo', '1d', df)
        loaded = self.downloader._load_cache('AAPL', '1mo', '1d')
        
        assert loaded is not None
        assert len(loaded) == 3
        assert loaded['Close'].iloc[0] == 100.5


class TestStockScorer:
    """Tests for stock scoring."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.scorer = StockScorer(cache_dir=self.temp_dir)
        
        # Create test data
        self.test_data = {}
        for symbol in ['AAPL', 'MSFT', 'GOOGL']:
            dates = pd.date_range(start='2024-01-01', periods=60, freq='D')
            df = pd.DataFrame({
                'Open': np.random.uniform(100, 150, 60),
                'High': np.random.uniform(150, 160, 60),
                'Low': np.random.uniform(90, 100, 60),
                'Close': np.random.uniform(100, 150, 60),
                'Volume': np.random.uniform(1e6, 2e6, 60),
            }, index=dates)
            self.test_data[symbol] = df
    
    def teardown_method(self):
        """Cleanup."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_score_stocks(self):
        """Test stock scoring."""
        scores = self.scorer.score_stocks(self.test_data)
        
        assert len(scores) == 3
        for symbol, score in scores.items():
            assert 0 <= score.overall_score <= 100
            assert score.trend_score >= 0
            assert score.volatility_score >= 0
            assert score.volume_score >= 0
            assert score.liquidity_score >= 0
    
    def test_score_ranking(self):
        """Test that scores are ranked correctly."""
        scores = self.scorer.score_stocks(self.test_data)
        
        # Check ranks are sequential
        ranks = [s.rank for s in scores.values()]
        assert sorted(ranks) == list(range(1, len(scores) + 1))
    
    def test_select_top_stocks(self):
        """Test selecting top stocks."""
        scores = self.scorer.score_stocks(self.test_data)
        selected = self.scorer.select_top_stocks(scores, top_n=2, min_score=0)
        
        assert len(selected) <= 2
        assert all(isinstance(s, str) for s in selected)


class TestPerformanceTracker:
    """Tests for performance tracking and learning."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = PerformanceTracker(db_path=os.path.join(self.temp_dir, 'perf.db'))
    
    def teardown_method(self):
        """Cleanup."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_record_winning_trade(self):
        """Test recording a winning trade."""
        self.tracker.record_trade('AAPL', entry_price=100, exit_price=110, quantity=100)
        
        perf = self.tracker.get_top_performers(top_n=1)
        assert len(perf) == 1
        assert perf[0].symbol == 'AAPL'
        assert perf[0].wins == 1
        assert perf[0].losses == 0
    
    def test_record_losing_trade(self):
        """Test recording a losing trade."""
        self.tracker.record_trade('MSFT', entry_price=100, exit_price=90, quantity=100)
        
        perf = self.tracker.get_top_performers(top_n=1)
        assert len(perf) == 1
        assert perf[0].symbol == 'MSFT'
        assert perf[0].wins == 0
        assert perf[0].losses == 1
    
    def test_win_rate_calculation(self):
        """Test win rate is calculated correctly."""
        self.tracker.record_trade('AAPL', entry_price=100, exit_price=110, quantity=100)
        self.tracker.record_trade('AAPL', entry_price=110, exit_price=100, quantity=100)
        
        perf = self.tracker.get_top_performers(top_n=1)
        assert perf[0].win_rate == 0.5


class TestPortfolioOptimizer:
    """Tests for portfolio optimization."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.optimizer = PortfolioOptimizer(max_position_pct=15, min_position_pct=2)
    
    def test_allocate_portfolio(self):
        """Test portfolio allocation."""
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        scores = {'AAPL': 80, 'MSFT': 70, 'GOOGL': 60}
        prices = {'AAPL': 150, 'MSFT': 300, 'GOOGL': 140}
        
        allocations = self.optimizer.allocate_portfolio(
            symbols=symbols,
            scores=scores,
            prices=prices,
            portfolio_value=100000,
        )
        
        assert len(allocations) == 3
        total_pct = sum(a.allocation_pct for a in allocations.values())
        assert 95 < total_pct <= 100  # Allow small rounding
    
    def test_position_size_limits(self):
        """Test that position sizes respect limits."""
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        scores = {'AAPL': 100, 'MSFT': 100, 'GOOGL': 100}
        prices = {'AAPL': 150, 'MSFT': 300, 'GOOGL': 140}
        
        allocations = self.optimizer.allocate_portfolio(
            symbols=symbols,
            scores=scores,
            prices=prices,
            portfolio_value=100000,
        )
        
        # All positions should be <= max position
        for alloc in allocations.values():
            assert alloc.allocation_pct <= 15.0


class TestRiskManager:
    """Tests for risk management."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.manager = RiskManager(
            max_daily_loss_pct=2.0,
            max_drawdown_pct=10.0,
            max_position_pct=10.0,
            max_positions=20,
        )
    
    def test_reset_daily(self):
        """Test daily reset."""
        self.manager.reset_daily(current_equity=100000)
        assert self.manager.today_start_equity == 100000
        assert self.manager.peak_equity == 100000
    
    def test_daily_loss_check(self):
        """Test daily loss limit."""
        self.manager.reset_daily(100000)
        
        # Small loss - should be OK
        is_safe, _ = self.manager.check_daily_loss(99500)
        assert is_safe is True
        
        # Large loss - should fail
        is_safe, _ = self.manager.check_daily_loss(97500)  # 2.5% loss
        assert is_safe is False
    
    def test_position_size_check(self):
        """Test position size limits."""
        # Under limit
        is_safe, _ = self.manager.check_position_size(8.0)
        assert is_safe is True
        
        # Over limit
        is_safe, _ = self.manager.check_position_size(12.0)
        assert is_safe is False
    
    def test_stop_loss_calculation(self):
        """Test stop loss price calculation."""
        stop_price = self.manager.calculate_stop_loss_price(entry_price=100)
        assert stop_price == 95.0  # 5% stop loss


class TestMLPredictor:
    """Tests for ML prediction (if sklearn available)."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.predictor = MLPredictor(model_dir=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_feature_extraction(self):
        """Test feature extraction from performance data."""
        from src.trading_bot.data.performance_tracker import StockPerformance
        
        perf = StockPerformance(
            symbol='AAPL',
            trades=10,
            wins=7,
            losses=3,
            avg_win_pct=2.0,
            avg_loss_pct=-1.5,
        )
        
        features = self.predictor._extract_features(perf)
        assert features is not None
        assert len(features) == len(self.predictor.feature_names)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
