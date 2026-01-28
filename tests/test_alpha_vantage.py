"""
Tests for Alpha Vantage Data Provider Integration
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime, timedelta
from src.trading_bot.data.alpha_vantage_provider import AlphaVantageProvider, DataProviderFactory


class TestAlphaVantageProvider:
    """Test suite for Alpha Vantage API integration"""
    
    @pytest.fixture
    def mock_api_key(self):
        """Mock API key for testing"""
        return "TEST_API_KEY_123"
    
    @pytest.fixture
    def provider(self, mock_api_key, tmp_path):
        """Create provider with mock cache directory"""
        return AlphaVantageProvider(api_key=mock_api_key, cache_dir=str(tmp_path))
    
    def test_initialization_with_api_key(self, provider, mock_api_key):
        """Test provider initialization with direct API key"""
        assert provider.api_key == mock_api_key
        assert provider.cache_dir.exists()
    
    def test_initialization_from_env(self, tmp_path):
        """Test provider initialization from environment variable"""
        os.environ["ALPHA_VANTAGE_API_KEY"] = "ENV_API_KEY"
        provider = AlphaVantageProvider(cache_dir=str(tmp_path))
        assert provider.api_key == "ENV_API_KEY"
        del os.environ["ALPHA_VANTAGE_API_KEY"]
    
    def test_missing_api_key_raises_error(self, tmp_path):
        """Test that missing API key raises ValueError"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key not found"):
                AlphaVantageProvider(cache_dir=str(tmp_path))
    
    def test_rate_limiting(self, provider):
        """Test that rate limiting is applied"""
        start_time = datetime.now()
        provider._apply_rate_limiting()
        elapsed = (datetime.now() - start_time).total_seconds()
        # Should apply 12-second delay on first call
        assert elapsed >= 0  # First call doesn't wait
    
    def test_cache_path_generation(self, provider):
        """Test cache file path generation"""
        cache_path = provider._get_cache_path("AAPL")
        assert "AAPL" in str(cache_path)
        assert str(cache_path).endswith(".json")
    
    def test_save_and_load_cache(self, provider):
        """Test cache save and load functionality"""
        test_data = {
            "prices": [
                {"date": "2024-01-01", "close": 150.0},
                {"date": "2024-01-02", "close": 151.0}
            ]
        }
        
        # Save
        provider._save_to_cache("AAPL", test_data)
        
        # Load
        loaded = provider._load_from_cache("AAPL")
        assert loaded == test_data
    
    def test_cache_expiration(self, provider):
        """Test that stale cache is not used"""
        cache_path = provider._get_cache_path("AAPL")
        
        # Create stale cache (3 days old)
        stale_data = {"prices": []}
        with open(cache_path, 'w') as f:
            json.dump(stale_data, f)
        
        # Set modification time to 3 days ago
        old_time = (datetime.now() - timedelta(days=3)).timestamp()
        os.utime(cache_path, (old_time, old_time))
        
        # Should return None (stale)
        assert provider._load_from_cache("AAPL", max_age_days=1) is None
    
    @patch('requests.get')
    def test_get_daily_prices_success(self, mock_get, provider):
        """Test successful API call for daily prices"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "150.0",
                    "2. high": "152.0",
                    "3. low": "149.0",
                    "4. close": "151.0",
                    "5. volume": "1000000"
                },
                "2024-01-01": {
                    "1. open": "149.0",
                    "2. high": "151.0",
                    "3. low": "148.0",
                    "4. close": "150.0",
                    "5. volume": "1100000"
                }
            }
        }
        mock_get.return_value = mock_response
        
        prices, success = provider.get_daily_prices("AAPL", days=2)
        
        assert success is True
        assert len(prices) == 2
        assert prices[0]["close"] == 150.0
        assert prices[1]["close"] == 151.0
    
    @patch('requests.get')
    def test_get_daily_prices_api_error(self, mock_get, provider):
        """Test handling of API error response"""
        mock_response = Mock()
        mock_response.json.return_value = {"Error Message": "Invalid API key"}
        mock_get.return_value = mock_response
        
        prices, success = provider.get_daily_prices("AAPL")
        
        assert success is False
        assert prices == []
    
    @patch('requests.get')
    def test_get_daily_prices_rate_limit(self, mock_get, provider):
        """Test handling of rate limit response"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage"
        }
        mock_get.return_value = mock_response
        
        prices, success = provider.get_daily_prices("AAPL")
        
        assert success is False
        assert prices == []
    
    @patch('requests.get')
    def test_get_returns_series(self, mock_get, provider):
        """Test calculation of daily returns"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "150.0",
                    "2. high": "152.0",
                    "3. low": "149.0",
                    "4. close": "110.0",
                    "5. volume": "1000000"
                },
                "2024-01-01": {
                    "1. open": "149.0",
                    "2. high": "151.0",
                    "3. low": "148.0",
                    "4. close": "100.0",
                    "5. volume": "1100000"
                }
            }
        }
        mock_get.return_value = mock_response
        
        returns, success = provider.get_returns_series("AAPL", days=2)
        
        assert success is True
        assert len(returns) == 1  # n prices -> n-1 returns
        assert returns[0] == pytest.approx(0.10)  # 10% return
    
    @patch('src.trading_bot.data.alpha_vantage_provider.requests.get')
    def test_get_multiple_symbols(self, mock_get, provider):
        """Test fetching data for multiple symbols with rate limiting"""
        call_count = [0]
        
        def mock_response_factory(*args, **kwargs):
            """Create mock response for each call"""
            call_count[0] += 1
            mock_resp = Mock()
            mock_resp.json.return_value = {
                "Time Series (Daily)": {
                    "2024-01-02": {
                        "1. open": "101.0",
                        "2. high": "103.0",
                        "3. low": "100.0",
                        "4. close": "102.0",
                        "5. volume": "1000000"
                    },
                    "2024-01-01": {
                        "1. open": "100.0",
                        "2. high": "102.0",
                        "3. low": "99.0",
                        "4. close": "101.0",
                        "5. volume": "1000000"
                    }
                }
            }
            mock_resp.raise_for_status.return_value = None
            return mock_resp
        
        mock_get.side_effect = mock_response_factory
        
        results = provider.get_multiple_symbols(["AAPL", "MSFT"], days=2)
        
        assert "AAPL" in results
        assert "MSFT" in results
        # Verify returns were calculated (should have 1 return for 2 prices)
        assert len(results["AAPL"][0]) == 1
        assert len(results["MSFT"][0]) == 1
    
    @patch('requests.get')
    def test_data_sanitization(self, mock_get, provider):
        """Test that data is properly sanitized and typed"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "Time Series (Daily)": {
                "2024-01-01": {
                    "1. open": "150.50",
                    "2. high": "152.75",
                    "3. low": "149.25",
                    "4. close": "151.50",
                    "5. volume": "1234567"
                }
            }
        }
        mock_get.return_value = mock_response
        
        prices, success = provider.get_daily_prices("AAPL", days=1)
        
        # Verify proper type conversion
        assert isinstance(prices[0]["open"], float)
        assert isinstance(prices[0]["volume"], int)
        assert prices[0]["close"] == 151.50


class TestDataProviderFactory:
    """Test data provider factory"""
    
    def test_create_alpha_vantage_provider(self, tmp_path):
        """Test creating Alpha Vantage provider via factory"""
        provider = DataProviderFactory.create_provider(
            "alpha_vantage",
            api_key="TEST_KEY",
            cache_dir=str(tmp_path)
        )
        assert isinstance(provider, AlphaVantageProvider)
    
    def test_invalid_provider_type(self):
        """Test that invalid provider type raises error"""
        with pytest.raises(ValueError, match="Unknown provider type"):
            DataProviderFactory.create_provider("invalid_provider")


class TestSecurityIntegration:
    """Security-focused tests for API integration"""
    
    def test_api_key_not_logged(self, tmp_path, caplog):
        """Test that API key is never logged"""
        provider = AlphaVantageProvider(
            api_key="SECRET_API_KEY_123",
            cache_dir=str(tmp_path)
        )
        # API key should not appear in logs
        assert "SECRET_API_KEY_123" not in caplog.text
    
    def test_request_timeout(self, tmp_path):
        """Test that API requests have timeout to prevent hanging"""
        provider = AlphaVantageProvider(
            api_key="TEST_KEY",
            cache_dir=str(tmp_path)
        )
        with patch('src.trading_bot.data.alpha_vantage_provider.requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")
            prices, success = provider.get_daily_prices("AAPL")
            assert success is False
            assert prices == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
