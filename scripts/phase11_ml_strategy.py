#!/usr/bin/env python3
"""
Phase 11: ML-Based Ensemble Strategy
Uses Random Forest + Gradient Boosting to learn optimal trading signals
Targets: Beat S&P 500 by 5%+ (6.1% annual)
"""

import sys
import logging
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.historical_data import HistoricalDataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Phase11MLStrategy:
    """ML-based strategy learning from historical patterns"""
    
    def __init__(self):
        self.data_fetcher = HistoricalDataFetcher()
        self.rf_model = None
        self.gb_model = None
        self.scaler = StandardScaler()
        self.benchmark = 0.011
        self.target = 0.061
        
    def fetch_data(self, symbols: List[str]) -> Dict[str, np.ndarray]:
        """Fetch all stock data"""
        data = {}
        for symbol in symbols:
            try:
                df = self.data_fetcher.fetch_stock_data(symbol)
                if df is not None and len(df) > 100:
                    data[symbol] = df['Close'].values
            except:
                pass
        return data
    
    def extract_features(self, prices: np.ndarray, lookback: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extract trading features from price history
        Features: MAs, RSI, MACD, momentum, volatility, trend, etc.
        Target: 1 if price goes up next 5 days, 0 otherwise
        """
        features = []
        targets = []
        
        if len(prices) < lookback + 10:
            return np.array([]), np.array([])
        
        for i in range(lookback, len(prices) - 5):
            price = prices[i]
            hist = prices[max(0, i-lookback):i+1]
            
            # 1. Moving Averages
            ma5 = np.mean(hist[-5:])
            ma10 = np.mean(hist[-10:])
            ma20 = np.mean(hist[-20:])
            ma50 = np.mean(hist[-min(50, len(hist)):])
            
            # 2. RSI
            deltas = np.diff(hist[-15:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            avg_gain = np.mean(gains) if np.mean(gains) > 0 else 0.001
            avg_loss = np.mean(losses) if np.mean(losses) > 0 else 0.001
            rsi = 100 - (100 / (1 + avg_gain/avg_loss))
            
            # 3. MACD
            ema12 = np.mean(hist[-12:])
            ema26 = np.mean(hist[-26:]) if len(hist) >= 26 else ema12
            macd = ema12 - ema26
            
            # 4. Momentum
            momentum_5 = (price - hist[-5]) / hist[-5]
            momentum_10 = (price - hist[-10]) / hist[-10]
            momentum_20 = (price - hist[-20]) / hist[-20]
            
            # 5. Volatility
            returns = np.diff(np.log(hist[-20:]))
            volatility = np.std(returns) * np.sqrt(252)
            
            # 6. Trend
            trend = (price - ma50) / ma50 if ma50 > 0 else 0
            
            # 7. Price position
            high20 = np.max(hist[-20:])
            low20 = np.min(hist[-20:])
            position = (price - low20) / (high20 - low20) if high20 > low20 else 0.5
            
            # 8. Volume proxy (price change magnitude)
            volume_proxy = np.mean(np.abs(np.diff(hist[-10:])))
            
            feature_vec = [
                ma5, ma10, ma20, ma50,
                rsi,
                macd,
                momentum_5, momentum_10, momentum_20,
                volatility,
                trend,
                position,
                volume_proxy,
                price,  # Absolute price helps with scale invariance
            ]
            
            features.append(feature_vec)
            
            # Target: 1 if price up next 5 days, 0 otherwise
            future_price = prices[i+5]
            target = 1 if future_price > price else 0
            targets.append(target)
        
        return np.array(features), np.array(targets)
    
    def train_models(self, data: Dict[str, np.ndarray]):
        """Train ML models on all available data"""
        logger.info("Training ML models...")
        
        all_features = []
        all_targets = []
        
        # Extract features from all stocks
        for i, (symbol, prices) in enumerate(data.items()):
            features, targets = self.extract_features(prices, lookback=50)
            if len(features) > 0:
                all_features.append(features)
                all_targets.append(targets)
                logger.info(f"[{i+1}/{len(data)}] {symbol}: {len(features)} samples")
        
        if not all_features:
            logger.error("No training data generated")
            return False
        
        # Combine all data
        X = np.vstack(all_features)
        y = np.concatenate(all_targets)
        
        logger.info(f"Total training samples: {len(X)}")
        logger.info(f"Positive samples: {np.sum(y)} ({100*np.sum(y)/len(y):.1f}%)")
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Random Forest
        logger.info("Training Random Forest...")
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=15,
            min_samples_split=10,
            min_samples_leaf=5,
            random_state=42,
            n_jobs=-1
        )
        self.rf_model.fit(X_scaled, y)
        
        # Train Gradient Boosting
        logger.info("Training Gradient Boosting...")
        self.gb_model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )
        self.gb_model.fit(X_scaled, y)
        
        # Feature importance
        importance = self.rf_model.feature_importances_
        features = ['MA5', 'MA10', 'MA20', 'MA50', 'RSI', 'MACD', 
                   'Mom5', 'Mom10', 'Mom20', 'Vol', 'Trend', 'Pos', 'Volume', 'Price']
        top_features = sorted(zip(features, importance), key=lambda x: x[1], reverse=True)[:5]
        logger.info("Top 5 Features:")
        for feat, imp in top_features:
            logger.info(f"  {feat}: {imp:.4f}")
        
        return True
    
    def predict_signal(self, prices: np.ndarray) -> int:
        """Generate trading signal using ML models"""
        if self.rf_model is None or len(prices) < 60:
            return 0
        
        features, _ = self.extract_features(prices[-60:], lookback=50)
        if len(features) == 0:
            return 0
        
        # Use last sample
        X = features[-1:].reshape(1, -1)
        X_scaled = self.scaler.transform(X)
        
        # Ensemble: average probabilities from both models
        rf_proba = self.rf_model.predict_proba(X_scaled)[0, 1]  # P(up)
        gb_proba = self.gb_model.predict_proba(X_scaled)[0, 1]  # P(up)
        
        avg_prob = (rf_proba + gb_proba) / 2
        
        # Signal: strong buy if P(up) > 0.6, strong sell if < 0.4
        if avg_prob > 0.6:
            return 1
        elif avg_prob < 0.4:
            return -1
        else:
            return 0
    
    def backtest(self, prices: np.ndarray) -> float:
        """Backtest using ML signals"""
        if len(prices) < 100 or self.rf_model is None:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        trans_cost = 0.001
        
        for i in range(100, len(prices)):
            price = prices[i]
            signal = self.predict_signal(prices[:i+1])
            
            # Execute trades
            if signal == 1 and position == 0:
                position = capital / price * (1 - trans_cost)
                capital = 0
            elif signal == -1 and position > 0:
                capital = position * price * (1 - trans_cost)
                position = 0
        
        if position > 0:
            capital = position * prices[-1] * (1 - trans_cost)
        
        total = (capital - 100000.0) / 100000.0
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        
        return annual
    
    def run(self):
        """Run Phase 11"""
        logger.info("="*80)
        logger.info("PHASE 11: ML-BASED ENSEMBLE STRATEGY")
        logger.info("="*80)
        
        symbols = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
            'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
            'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
            'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
            'CPRT', 'CHKP'
        ]
        
        # Fetch data
        logger.info(f"Fetching {len(symbols)} stocks...")
        data = self.fetch_data(symbols)
        logger.info(f"Fetched {len(data)} stocks\n")
        
        # Train models
        if not self.train_models(data):
            logger.error("Failed to train models")
            return
        
        # Backtest
        logger.info("\nRunning backtests...")
        results = []
        annuals = []
        
        for i, (symbol, prices) in enumerate(data.items(), 1):
            annual = self.backtest(prices)
            annuals.append(annual)
            results.append({'Symbol': symbol, 'Annual_Return': annual})
            logger.info(f"[{i:2d}/{len(data)}] {symbol:6s}: {annual:7.4f}")
        
        avg = np.mean(annuals)
        
        # Report
        logger.info(f"\n{'='*80}")
        logger.info(f"PHASE 11: ML-BASED ENSEMBLE STRATEGY")
        logger.info(f"{'='*80}")
        logger.info(f"Avg Annual Return:      {avg:7.4f} ({avg*100:6.2f}%)")
        logger.info(f"S&P 500 Benchmark:      {self.benchmark:7.4f} ({self.benchmark*100:6.2f}%)")
        logger.info(f"Outperformance:         {(avg - self.benchmark):7.4f} ({(avg - self.benchmark)*100:6.2f}%)")
        logger.info(f"Target (5%+ / 6.1%):    {self.target:7.4f} ({self.target*100:6.2f}%)")
        logger.info(f"Beats Target:           {'YES! ✓' if avg >= self.target else 'NO'}")
        logger.info(f"Stocks Beating S&P:     {sum(1 for a in annuals if a > self.benchmark)}/{len(annuals)}")
        logger.info(f"Best Stock:             {max(zip(data.keys(), annuals), key=lambda x: x[1])[0]} ({max(annuals):.4f})")
        logger.info(f"Worst Stock:            {min(zip(data.keys(), annuals), key=lambda x: x[1])[0]} ({min(annuals):.4f})")
        logger.info(f"Median Return:          {np.median(annuals):7.4f}")
        logger.info(f"Std Dev:                {np.std(annuals):7.4f}")
        logger.info(f"{'='*80}\n")
        
        # Save
        out = Path(__file__).parent.parent.parent / 'phase11_results'
        out.mkdir(exist_ok=True)
        
        pd.DataFrame(results).to_csv(out / 'phase11_ml_results.csv', index=False)
        
        with open(out / 'PHASE11_ML_RESULTS.txt', 'w') as f:
            f.write("PHASE 11: ML-BASED ENSEMBLE STRATEGY\n")
            f.write("="*80 + "\n\n")
            f.write("ARCHITECTURE:\n")
            f.write("  Ensemble: Random Forest + Gradient Boosting\n")
            f.write("  Training: Supervised learning on historical patterns\n\n")
            f.write("FEATURES LEARNED:\n")
            f.write("  - Moving Averages (5, 10, 20, 50 day)\n")
            f.write("  - RSI (14 period)\n")
            f.write("  - MACD (12/26)\n")
            f.write("  - Momentum (5, 10, 20 day)\n")
            f.write("  - Volatility (annualized)\n")
            f.write("  - Trend strength\n")
            f.write("  - Price position\n")
            f.write("  - Volume proxy\n\n")
            f.write(f"RESULTS:\n")
            f.write(f"  Avg Annual Return:   {avg:.4f} ({avg*100:.2f}%)\n")
            f.write(f"  S&P 500 Benchmark:   {self.benchmark:.4f}\n")
            f.write(f"  Outperformance:      {(avg - self.benchmark):.4f}\n")
            f.write(f"  Target:              {self.target:.4f}\n")
            f.write(f"  Beats Target:        {'YES! ✓' if avg >= self.target else 'NO'}\n\n")
            f.write("TOP 10 PERFORMERS:\n")
            top = sorted(enumerate(annuals), key=lambda x: x[1], reverse=True)[:10]
            syms = list(data.keys())
            for rank, (idx, ann) in enumerate(top, 1):
                f.write(f"  {rank:2d}. {syms[idx]:6s}: {ann:7.4f} ({ann*100:6.2f}%)\n")
        
        logger.info(f"Results saved to {out}")


if __name__ == '__main__':
    Phase11MLStrategy().run()
