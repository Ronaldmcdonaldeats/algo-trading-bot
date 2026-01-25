"""Volatility regime detection and adaptive position sizing."""

import pandas as pd
import numpy as np


class VolatilityRegime:
    """Detect market volatility regime and adjust strategy parameters."""
    
    # Volatility thresholds (in basis points)
    LOW_VOLATILITY_BPS = 50  # < 0.5% daily move
    MEDIUM_VOLATILITY_BPS = 150  # 0.5% - 1.5% daily move
    HIGH_VOLATILITY_BPS = 300  # > 1.5% daily move
    
    @staticmethod
    def calculate_volatility_metrics(close_prices: pd.Series, high_prices: pd.Series = None, 
                                     low_prices: pd.Series = None, period: int = 20) -> dict:
        """Calculate comprehensive volatility metrics.
        
        Args:
            close_prices: Series of closing prices
            high_prices: Series of high prices (optional)
            low_prices: Series of low prices (optional)
            period: Lookback period for calculation
            
        Returns:
            Dict with volatility metrics:
            - daily_volatility_pct: Daily price change volatility
            - intraday_volatility_pct: High-low range volatility (if provided)
            - atr_volatility_pct: ATR-based volatility
            - realized_volatility_pct: Historical volatility
            - volatility_regime: "LOW", "MEDIUM", "HIGH"
        """
        if close_prices is None or len(close_prices) < period:
            return {
                "daily_volatility_pct": 0,
                "intraday_volatility_pct": 0,
                "atr_volatility_pct": 0,
                "realized_volatility_pct": 0,
                "volatility_regime": "MEDIUM",
            }
        
        # Daily volatility (price change from close to close)
        returns = close_prices.pct_change().tail(period)
        daily_vol = returns.std() * 100  # Convert to percentage
        daily_vol_bps = daily_vol * 100  # Convert to basis points
        
        # Intraday volatility (high-low range)
        intraday_vol = 0
        if high_prices is not None and low_prices is not None:
            hl_range = ((high_prices - low_prices) / close_prices * 100).tail(period)
            intraday_vol = hl_range.mean()
        
        # ATR volatility
        atr_vol = VolatilityRegime.calculate_atr_volatility(high_prices, low_prices, close_prices, period)
        
        # Realized volatility (standard deviation of returns)
        realized_vol = daily_vol
        
        # Determine regime based on combined metrics
        regime = VolatilityRegime.get_regime_from_volatility(daily_vol_bps)
        
        return {
            "daily_volatility_pct": round(daily_vol, 3),
            "intraday_volatility_pct": round(intraday_vol, 3),
            "atr_volatility_pct": round(atr_vol, 3),
            "realized_volatility_pct": round(realized_vol, 3),
            "volatility_regime": regime,
            "daily_volatility_bps": round(daily_vol_bps, 1),
        }

    @staticmethod
    def calculate_atr_volatility(high_prices: pd.Series, low_prices: pd.Series, 
                                  close_prices: pd.Series, period: int = 14) -> float:
        """Calculate ATR-based volatility as percentage of close price.
        
        Args:
            high_prices: Series of high prices
            low_prices: Series of low prices
            close_prices: Series of close prices
            period: ATR period
            
        Returns:
            ATR volatility as percentage
        """
        if high_prices is None or low_prices is None or close_prices is None:
            return 0
        
        if len(high_prices) < period:
            return 0
        
        # Calculate true range
        tr1 = high_prices - low_prices
        tr2 = abs(high_prices - close_prices.shift())
        tr3 = abs(low_prices - close_prices.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR
        atr = tr.rolling(window=period).mean()
        atr_latest = atr.iloc[-1]
        close_latest = close_prices.iloc[-1]
        
        if close_latest <= 0:
            return 0
        
        atr_volatility = (atr_latest / close_latest) * 100
        return atr_volatility

    @staticmethod
    def get_regime_from_volatility(volatility_bps: float) -> str:
        """Classify volatility regime based on basis points.
        
        Args:
            volatility_bps: Volatility in basis points
            
        Returns:
            "LOW", "MEDIUM", or "HIGH"
        """
        if volatility_bps < VolatilityRegime.LOW_VOLATILITY_BPS:
            return "LOW"
        elif volatility_bps < VolatilityRegime.MEDIUM_VOLATILITY_BPS:
            return "MEDIUM"
        else:
            return "HIGH"

    @staticmethod
    def get_position_size_adjustment(regime: str, aggressive: bool = False) -> float:
        """Get position size multiplier based on volatility regime.
        
        Args:
            regime: "LOW", "MEDIUM", or "HIGH"
            aggressive: If True, more aggressive sizing (1.5x vs 1.0x in high vol)
            
        Returns:
            Position size multiplier (0.5 - 1.5)
            
        Logic:
        - LOW volatility: Increase position size (less risky)
        - MEDIUM volatility: Normal position size
        - HIGH volatility: Reduce position size (more risky)
        """
        if regime == "LOW":
            return 1.5 if aggressive else 1.2  # Increase size
        elif regime == "MEDIUM":
            return 1.0  # Normal
        else:  # HIGH
            return 0.5 if aggressive else 0.7  # Decrease size

    @staticmethod
    def get_stop_loss_adjustment(regime: str) -> float:
        """Get stop-loss adjustment based on volatility regime.
        
        Args:
            regime: "LOW", "MEDIUM", or "HIGH"
            
        Returns:
            Stop-loss multiplier for ATR-based calculation
            
        Logic:
        - LOW volatility: Tighter stops (1.5x ATR)
        - MEDIUM volatility: Normal stops (2.0x ATR)
        - HIGH volatility: Wider stops (3.0x ATR)
        """
        if regime == "LOW":
            return 1.5  # Tighter
        elif regime == "MEDIUM":
            return 2.0  # Normal
        else:  # HIGH
            return 3.0  # Wider

    @staticmethod
    def get_profit_target_adjustment(regime: str) -> float:
        """Get profit target adjustment based on volatility regime.
        
        Args:
            regime: "LOW", "MEDIUM", or "HIGH"
            
        Returns:
            Profit target multiplier for ATR-based calculation
            
        Logic:
        - LOW volatility: Tight targets (2.5x ATR)
        - MEDIUM volatility: Normal targets (3.0x ATR)
        - HIGH volatility: Loose targets (5.0x ATR)
        """
        if regime == "LOW":
            return 2.5  # Tight
        elif regime == "MEDIUM":
            return 3.0  # Normal
        else:  # HIGH
            return 5.0  # Loose

    @staticmethod
    def get_win_rate_expectation(regime: str) -> dict:
        """Get expected win rate and reward-risk ratio by regime.
        
        Args:
            regime: "LOW", "MEDIUM", or "HIGH"
            
        Returns:
            Dict with expected metrics:
            - expected_win_rate: Win percentage (0-1)
            - expected_reward_risk: Risk-reward ratio
            - expected_sharpe: Expected Sharpe ratio
        """
        if regime == "LOW":
            return {
                "expected_win_rate": 0.55,  # 55% wins (easier to trade)
                "expected_reward_risk": 2.0,  # 2:1 risk-reward
                "expected_sharpe": 1.2,
                "holding_period_days": 1,  # Quick scalps
            }
        elif regime == "MEDIUM":
            return {
                "expected_win_rate": 0.52,  # 52% wins (balanced)
                "expected_reward_risk": 1.5,  # 1.5:1 risk-reward
                "expected_sharpe": 0.8,
                "holding_period_days": 2,  # Swing trades
            }
        else:  # HIGH
            return {
                "expected_win_rate": 0.48,  # 48% wins (harder to trade)
                "expected_reward_risk": 1.0,  # 1:1 risk-reward
                "expected_sharpe": 0.4,
                "holding_period_days": 5,  # Longer holds for better R:R
            }

    @staticmethod
    def get_strategy_adjustment_params(regime: str) -> dict:
        """Get strategy parameter adjustments based on volatility regime.
        
        Args:
            regime: "LOW", "MEDIUM", or "HIGH"
            
        Returns:
            Dict with strategy parameter adjustments:
            - rsi_oversold: RSI threshold for oversold (lower = more selective)
            - rsi_overbought: RSI threshold for overbought
            - macd_threshold: MACD signal strength threshold
            - bollinger_std_dev: Bollinger Band std dev multiplier
            - signal_confidence: Confidence threshold for trade (0-1)
        """
        if regime == "LOW":
            return {
                "rsi_oversold": 25,  # More selective (default 30)
                "rsi_overbought": 75,
                "macd_threshold": 0.02,  # Stricter MACD signal
                "bollinger_std_dev": 2.0,  # Normal bands
                "signal_confidence": 0.7,  # Require higher confidence
                "min_bars_in_signal": 3,  # Need more confirmation
            }
        elif regime == "MEDIUM":
            return {
                "rsi_oversold": 30,  # Normal (default)
                "rsi_overbought": 70,
                "macd_threshold": 0.015,
                "bollinger_std_dev": 2.0,
                "signal_confidence": 0.5,  # Normal confidence
                "min_bars_in_signal": 2,
            }
        else:  # HIGH
            return {
                "rsi_oversold": 40,  # Less selective (higher threshold)
                "rsi_overbought": 60,
                "macd_threshold": 0.01,  # Looser MACD signal
                "bollinger_std_dev": 2.5,  # Wider bands
                "signal_confidence": 0.3,  # Lower confidence OK
                "min_bars_in_signal": 1,  # Quick signals
            }

    @staticmethod
    def print_regime_analysis(regime_metrics: dict) -> None:
        """Print formatted volatility regime analysis.
        
        Args:
            regime_metrics: Dict from calculate_volatility_metrics()
        """
        print(f"[VOLATILITY] Regime: {regime_metrics['volatility_regime']} | "
              f"Daily Vol: {regime_metrics['daily_volatility_pct']:.3f}% | "
              f"Intraday: {regime_metrics['intraday_volatility_pct']:.3f}% | "
              f"ATR Vol: {regime_metrics['atr_volatility_pct']:.3f}%")
