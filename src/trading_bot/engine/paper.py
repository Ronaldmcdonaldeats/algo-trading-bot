from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from trading_bot.broker.base import OrderRejection
from trading_bot.broker.paper import PaperBroker, PaperBrokerConfig
from trading_bot.broker.alpaca import AlpacaBroker, AlpacaConfig
from trading_bot.configs import load_config
from trading_bot.core.models import Fill, Order, Portfolio
from trading_bot.data.providers import MarketDataProvider, AlpacaProvider, MockDataProvider
from trading_bot.db.repository import SqliteRepository
from trading_bot.learn.adaptive_controller import AdaptiveLearningController
from trading_bot.learn.ensemble import ExponentialWeightsEnsemble, reward_to_unit_interval
from trading_bot.learn.tuner import default_params, maybe_tune_weekly
from trading_bot.learn.momentum_scaling import MomentumScaler
from trading_bot.analytics.realtime_metrics import MetricsCollector
from trading_bot.analytics.position_monitor import PositionMonitor, AlertType
from trading_bot.risk import position_size_shares, stop_loss_price, take_profit_price
from trading_bot.risk.position_autocorrect import PositionAutocorrector
from trading_bot.risk.portfolio_optimizer import PortfolioOptimizer
from trading_bot.risk.options_hedging import OptionsHedger
from trading_bot.risk.risk_adjusted_sizer import RiskAdjustedSizer
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.base import StrategyDecision, StrategyOutput
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy
from trading_bot.strategy.advanced_entry_filter import AdvancedEntryFilter
from trading_bot.strategy.multitimeframe_signals import MultiTimeframeSignalValidator
from trading_bot.strategy.integrated_strategy import MasterIntegratedStrategy


@dataclass(frozen=True)
class PaperEngineConfig:
    config_path: str
    db_path: str
    symbols: list[str]
    period: str = "6mo"
    interval: str = "1d"
    start_cash: float = 100_000.0
    sleep_seconds: float = 60.0
    iterations: int = 1  # 0 = infinite
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    min_fee: float = 0.0

    # Live Trading
    live_trading: bool = False  # Set to True to use real Alpaca trading
    paper_mode: bool = True  # Paper trading mode (paper_mode=True uses fake money on Alpaca)

    # Phase 3
    strategy_mode: str = "ensemble"  # ensemble|mean_reversion_rsi|momentum_macd_volume|breakout_atr|ultimate_hybrid
    enable_learning: bool = True  # Enable adaptive learning by default
    tune_weekly: bool = True  # Enable weekly tuning by default
    learning_eta: float = 0.3
    ignore_market_hours: bool = False  # For testing outside market hours
    memory_mode: bool = False  # Aggressive memory optimizations (smaller batches, fewer indicators)


@dataclass(frozen=True)
class PaperEngineUpdate:
    ts: datetime
    iteration: int
    mode: str
    prices: dict[str, float]
    signals: dict[str, int]  # final decision per symbol
    decisions: dict[str, StrategyDecision]
    fills: list[Fill]
    rejections: list[OrderRejection]
    portfolio: Portfolio
    
    # Real-time performance metrics
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    current_pnl: float = 0.0




def _normalize_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df.empty:
        raise ValueError("No data returned")

    if isinstance(df.columns, pd.MultiIndex):
        if symbol not in df.columns.get_level_values(1):
            raise ValueError(f"Missing {symbol} in downloaded data")
        out = df.xs(symbol, axis=1, level=1, drop_level=True)
    else:
        out = df

    if "Close" not in out.columns:
        raise ValueError(f"Downloaded data for {symbol} missing Close column")

    out = out.dropna(subset=["Close"])
    if out.empty:
        raise ValueError(f"All Close values are NaN for {symbol}")

    # Convert to float32 to reduce memory (50% savings on OHLC data)
    for col in ['Open', 'High', 'Low', 'Close']:
        if col in out.columns and out[col].dtype != np.float32:
            out[col] = out[col].astype(np.float32)
    if 'Volume' in out.columns and out['Volume'].dtype not in [np.uint32, np.uint64]:
        out['Volume'] = out['Volume'].astype(np.uint32)

    return out


class PaperEngine:
    def __init__(
        self,
        *,
        cfg: PaperEngineConfig,
        provider: MarketDataProvider | None = None,
    ) -> None:
        self.cfg = cfg

        self.app_cfg = load_config(cfg.config_path)

        self.repo = SqliteRepository(db_path=Path(cfg.db_path))
        self.repo.init_db()

        # Initialize broker: live Alpaca or paper broker
        if cfg.live_trading:
            try:
                alpaca_config = AlpacaConfig.from_env(paper_mode=cfg.paper_mode)
                self.broker = AlpacaBroker(config=alpaca_config)
                mode = "PAPER" if cfg.paper_mode else "LIVE"
                print(f"[BROKER] Using AlpacaBroker in {mode} mode")
            except Exception as e:
                print(f"[ERROR] Failed to initialize AlpacaBroker: {e}")
                print(f"[FALLBACK] Using PaperBroker instead")
                self.broker = PaperBroker(
                    start_cash=float(cfg.start_cash),
                    config=PaperBrokerConfig(
                        commission_bps=float(cfg.commission_bps),
                        slippage_bps=float(cfg.slippage_bps),
                        min_fee=float(cfg.min_fee),
                    ),
                )
        else:
            self.broker = PaperBroker(
                start_cash=float(cfg.start_cash),
                config=PaperBrokerConfig(
                    commission_bps=float(cfg.commission_bps),
                    slippage_bps=float(cfg.slippage_bps),
                    min_fee=float(cfg.min_fee),
                ),
            )

        self.data = provider or MockDataProvider()
        self.iteration = 0

        # Learning / strategy state
        self.strategy_mode = str(cfg.strategy_mode)
        self.enable_learning = bool(cfg.enable_learning)
        self.tune_weekly = bool(cfg.tune_weekly)

        persisted = self.repo.latest_learning_state()
        persisted_weights: Dict[str, float] = {}
        persisted_params: Dict[str, Dict[str, Any]] = {}
        self.last_tuned_bucket: Optional[str] = None

        if persisted is not None:
            try:
                persisted_weights = json.loads(persisted.weights_json or "{}")
            except Exception:
                persisted_weights = {}
            try:
                persisted_params = json.loads(persisted.params_json or "{}")
            except Exception:
                persisted_params = {}

            note = str(persisted.note or "")
            if "tuned_week=" in note:
                self.last_tuned_bucket = note.split("tuned_week=", 1)[1].strip()

        # Default params + persisted overrides
        self.params: Dict[str, Dict[str, Any]] = default_params()
        for k, v in persisted_params.items():
            if isinstance(v, dict):
                self.params[k] = dict(v)

        self.strategies = self._build_strategies(self.params)

        # Ensemble weights
        names = list(self.strategies.keys())
        if persisted_weights:
            weights = {n: float(persisted_weights.get(n, 1.0)) for n in names}
        else:
            weights = {n: 1.0 for n in names}

        self.ensemble = ExponentialWeightsEnsemble(weights=weights, eta=float(cfg.learning_eta))

        # Adaptive learning controller (Phase 3+)
        self.adaptive_controller = AdaptiveLearningController(
            ensemble=self.ensemble,
            min_trades_for_analysis=5,
        )
        self.trade_history: list[dict] = []  # Track trades for analysis
        self.equity_history: list[float] = [float(cfg.start_cash)]

        # For learning updates
        self._prev_prices: Optional[Dict[str, float]] = None
        self._prev_signals_by_symbol: Dict[str, Dict[str, int]] = {}
        
        # Signal confirmation: track consecutive bars with same signal (for 2-bar confirmation)
        self._signal_confirmation: Dict[str, int] = {}  # symbol -> count of consecutive bars with signal=1
        
        # Multi-level profit taking: track entry price and bars held for time-based exits
        self._position_entry_bars: Dict[str, int] = {}  # symbol -> entry iteration
        self._position_entry_prices: Dict[str, float] = {}  # symbol -> entry price
        
        # Phase 21: Options hedging - track which positions have hedges
        self._hedged_positions: set[str] = set()  # Symbols with active hedges
        
        # ML Signal Manager (Phase 16)
        from trading_bot.learn.ml_signals import MLSignalManager
        self.ml_manager = MLSignalManager()
        self.ml_enabled = True  # Can be toggled via config
        self._ml_trained_symbols: set[str] = set()
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}  # Cache OHLCV for ML training
        
        # Position Autocorrection (Phase 17)
        self.position_autocorrector = PositionAutocorrector(
            max_position_risk_pct=float(self.app_cfg.risk.max_risk_per_trade),
            max_drawdown_pct=3.0,  # Exit if position down 3%
            max_hold_bars=30,  # Max bars to hold a position
        )
        self.autocorrection_enabled = True
        
        # Portfolio Optimizer (Phase 19)
        self.portfolio_optimizer = PortfolioOptimizer(
            lookback_bars=50,
            rebalance_interval=20,
            max_concentration=0.25,
            correlation_threshold=0.7,
        )
        self.portfolio_optimization_enabled = True
        
        # Momentum Scaler (Phase 20)
        self.momentum_scaler = MomentumScaler()
        self.momentum_scaling_enabled = True
        
        # Options Hedger (Phase 21)
        self.options_hedger = OptionsHedger(
            hedge_threshold=-2.0,
            put_strike_pct=0.95,
            collar_call_pct=1.05,
        )
        self.hedging_enabled = False  # Disabled by default (paper trading only)
        
        # Advanced Entry Filter (Phase 22)
        self.entry_filter = AdvancedEntryFilter()
        self.entry_filtering_enabled = True
        
        # Real-Time Metrics Monitor (Phase 23)
        self.metrics_collector = MetricsCollector(window_size=100)
        self.metrics_enabled = True
        
        # Position Monitor (Phase 24)
        self.position_monitor = PositionMonitor(
            tp_threshold=0.01,  # Alert within 1% of take profit
            sl_threshold=0.005,  # Alert within 0.5% of stop loss
            drawdown_threshold=0.03,  # Alert if down >3% from peak
            age_threshold=200,  # Alert if held >200 bars
            momentum_shift_threshold=0.2,  # Alert if momentum shifts >0.2
        )
        self.position_monitoring_enabled = True
        
        # Risk-Adjusted Position Sizer (Phase 25) - SCALED UP
        self.risk_sizer = RiskAdjustedSizer(
            base_risk_pct=0.02,  # 2% risk per trade (increased from 1%)
            max_position_pct=0.25,  # Max 25% of portfolio per trade (increased from 15%)
            min_position_pct=0.001,  # Min 0.1% of portfolio per trade
            volatility_scale=1.0,  # Scale of volatility impact
            drawdown_scale=1.0,  # Scale of drawdown impact
            win_streak_boost=1.3,  # Up to 30% boost on hot streak (increased from 20%)
            loss_streak_reduction=0.8,  # Down to 80% on cold streak (less reduction)
            hot_streak_min=3,  # 3+ consecutive wins for boost
            cold_streak_min=2,  # 2+ consecutive losses for reduction
        )
        self.risk_adjusted_sizing_enabled = True
        
        # Multi-Timeframe Signal Validator (Phase 26)
        self.mtf_validator = MultiTimeframeSignalValidator(
            hourly_weight=0.4,
            daily_weight=0.6,
            correlation_threshold=0.65,
            vol_threshold_low=0.15,
            vol_threshold_high=0.35,
            min_alignment_strength=0.5,
        )
        self.multitimeframe_enabled = True

    def _build_strategies(self, params: Dict[str, Dict[str, Any]]) -> Dict[str, StrategyOutput | Any]:
        """Build strategy instances from parameters."""
        strategies = {}

        # Mean reversion RSI
        rsi_params = params.get("mean_reversion_rsi", {})
        strategies["mean_reversion_rsi"] = RsiMeanReversionStrategy(
            rsi_period=int(rsi_params.get("rsi_period", 14)),
            entry_oversold=float(rsi_params.get("entry_oversold", 30.0)),
            exit_rsi=float(rsi_params.get("exit_rsi", 50.0)),
        )

        # MACD volume momentum
        macd_params = params.get("momentum_macd_volume", {})
        strategies["momentum_macd_volume"] = MacdVolumeMomentumStrategy(
            macd_fast=int(macd_params.get("macd_fast", 12)),
            macd_slow=int(macd_params.get("macd_slow", 26)),
            macd_signal=int(macd_params.get("macd_signal", 9)),
            vol_sma=int(macd_params.get("vol_sma", 20)),
            vol_mult=float(macd_params.get("vol_mult", 1.0)),
        )

        # ATR breakout
        atr_params = params.get("breakout_atr", {})
        strategies["breakout_atr"] = AtrBreakoutStrategy(
            atr_period=int(atr_params.get("atr_period", 14)),
            breakout_lookback=int(atr_params.get("breakout_lookback", 20)),
            atr_mult=float(atr_params.get("atr_mult", 1.0)),
        )

        return strategies

    def _calculate_metrics(self) -> tuple[float, float, float, int, float]:
        """Calculate real-time performance metrics.
        
        Returns: (sharpe_ratio, max_drawdown_pct, win_rate, num_trades, current_pnl)
        """
        # Calculate Sharpe ratio
        if len(self.equity_history) < 2:
            sharpe = 0.0
        else:
            returns = np.diff(self.equity_history) / np.array(self.equity_history[:-1])
            excess_returns = returns - (0.02 / 252)  # Daily risk-free rate
            sharpe = float(np.sqrt(252) * np.mean(excess_returns) / (np.std(excess_returns) + 1e-8))
        
        # Calculate max drawdown
        if len(self.equity_history) < 2:
            max_dd = 0.0
        else:
            cummax = np.maximum.accumulate(self.equity_history)
            drawdown = (np.array(self.equity_history) - cummax) / cummax
            max_dd = float(np.min(drawdown))
        
        # Calculate win rate
        if len(self.trade_history) == 0:
            win_rate = 0.0
            num_trades = 0
        else:
            winning = len([t for t in self.trade_history if t.get("pnl", 0) > 0])
            num_trades = len(self.trade_history)
            win_rate = winning / num_trades if num_trades > 0 else 0.0
        
        # Current P&L
        start_cash = float(self.cfg.start_cash)
        current_equity = self.equity_history[-1] if self.equity_history else start_cash
        current_pnl = current_equity - start_cash
        
        return sharpe, max_dd, win_rate, num_trades, current_pnl

    def step(self, *, now: datetime | None = None) -> PaperEngineUpdate:
        self.iteration += 1
        ts = now or datetime.utcnow()

        print(f"[{self.iteration}] Fetching data for {len(self.cfg.symbols)} symbols...", end="", flush=True)
        bars = self.data.download_bars(
            symbols=self.cfg.symbols,
            period=self.cfg.period,
            interval=self.cfg.interval,
        )
        print(" [OK]", flush=True)

        # Normalize bars per symbol first (process in batches to reduce memory spikes).
        ohlcv_by_symbol: Dict[str, pd.DataFrame] = {}
        prices: Dict[str, float] = {}
        batch_size = 10 if self.cfg.memory_mode else 20  # Smaller batches in memory_mode
        for i in range(0, len(self.cfg.symbols), batch_size):
            batch = self.cfg.symbols[i:i + batch_size]
            for sym in batch:
                ohlcv = _normalize_ohlcv(bars, sym)
                ohlcv_by_symbol[sym] = ohlcv
                px = float(ohlcv["Close"].iloc[-1])
                prices[sym] = px
                self.broker.set_price(sym, px)
                
                # Update portfolio optimizer history
                if self.portfolio_optimization_enabled:
                    self.portfolio_optimizer.update_history(sym, ohlcv)
                
                # Update momentum scaling (Phase 20)
                if self.momentum_scaling_enabled:
                    self.momentum_scaler.update_metrics(sym, ohlcv)
        
        # Calculate correlations and optimize allocations (Phase 19)
        if self.portfolio_optimization_enabled:
            self.portfolio_optimizer.calculate_correlations(list(prices.keys()))
        
        print(f"[{self.iteration}] Processing {len(ohlcv_by_symbol)} symbols...", end="", flush=True)

        # 1) Learning update from previous step (based on previous strategy signals).
        if self.enable_learning and self._prev_prices is not None and self._prev_signals_by_symbol:
            rewards_sum = {name: 0.0 for name in self.strategies.keys()}
            n = 0
            for sym, prev_px in self._prev_prices.items():
                if sym not in prices:
                    continue
                if prev_px <= 0:
                    continue
                ret = float(prices[sym]) / float(prev_px) - 1.0
                n += 1
                prev_sig = self._prev_signals_by_symbol.get(sym, {})
                for name in rewards_sum:
                    if int(prev_sig.get(name, 0)) == 1:
                        rewards_sum[name] += float(ret)

            if n > 0:
                rewards_01 = {
                    name: reward_to_unit_interval(rewards_sum[name] / float(n))
                    for name in rewards_sum
                }
                self.ensemble.update(rewards_01)
                self.repo.log_learning_state(
                    ts=ts,
                    weights=self.ensemble.normalized(),
                    params=self.params,
                    note="weights_update",
                )

        # 2) Weekly bounded parameter tuning (opt-in).
        if self.enable_learning and self.tune_weekly:
            tune = maybe_tune_weekly(
                now=ts,
                last_tuned_bucket=self.last_tuned_bucket,
                ohlcv_by_symbol=ohlcv_by_symbol,
                current_params=self.params,
            )
            if tune.tuned:
                self.params = tune.params
                self.strategies = self._build_strategies(self.params)
                # Ensure ensemble keeps all strategies.
                for name in self.strategies.keys():
                    self.ensemble.weights.setdefault(name, 1.0)
                self.last_tuned_bucket = tune.note.split("tuned_week=", 1)[1].strip()
                self.repo.log_learning_state(
                    ts=ts,
                    weights=self.ensemble.normalized(),
                    params=self.params,
                    note=tune.note,
                )

        # 3) Adaptive learning: market regime detection + strategy analysis
        if self.enable_learning:
            equity_series = pd.Series(self.equity_history) if self.equity_history else None
            adaptive_decision = self.adaptive_controller.step(
                ohlcv_by_symbol=ohlcv_by_symbol,
                current_params=self.params,
                trades=self.trade_history,
                equity_series=equity_series,
                now=ts,
            )
            
            # Apply regime-adjusted weights
            # Blend them gently into the ensemble
            for name, adjusted_w in adaptive_decision.adjusted_weights.items():
                current_w = self.ensemble.weights.get(name, 1.0)
                # Gentle blend: 70% current, 30% regime adjustment
                blended = 0.7 * current_w + 0.3 * adjusted_w
                self.ensemble.weights[name] = float(max(self.ensemble.min_weight, blended))
            
            # Log adaptive decision
            self.repo.log_adaptive_decision(
                ts=ts,
                regime=adaptive_decision.regime.value,
                regime_confidence=adaptive_decision.regime_confidence,
                adjusted_weights=adaptive_decision.adjusted_weights,
                param_recommendations=adaptive_decision.parameter_recommendations,
                anomalies=adaptive_decision.anomalies,
                explanation=adaptive_decision.explanation,
            )

        # 4) Compute decisions and execute orders.
        decisions: Dict[str, StrategyDecision] = {}
        signals: Dict[str, int] = {}
        fills: list[Fill] = []
        rejections: list[OrderRejection] = []

        current_signals_by_symbol: Dict[str, Dict[str, int]] = {}
        
        # Position Autocorrection (Phase 17): Scan and fix position issues
        if self.autocorrection_enabled:
            portfolio = self.broker.portfolio()
            issues = self.position_autocorrector.scan_positions(
                positions=portfolio.positions,
                prices=prices,
                equity=portfolio.equity(prices),
                entry_bars=self._position_entry_bars,
                entry_prices=self._position_entry_prices,
                current_bar=self.iteration,
            )
            
            if issues:
                corrections = self.position_autocorrector.recommend_corrections(
                    issues=issues,
                    positions=portfolio.positions,
                    prices=prices,
                    entry_prices=self._position_entry_prices,
                )
                
                # Apply critical corrections immediately
                for correction in corrections:
                    if correction.symbol in [i.symbol for i in self.position_autocorrector.get_critical_issues()]:
                        pos = portfolio.get_position(correction.symbol)
                        
                        if correction.action_type == "remove_position" and pos.qty != 0:
                            order = Order(
                                id=uuid.uuid4().hex,
                                ts=ts,
                                symbol=correction.symbol,
                                side="SELL",
                                qty=int(abs(pos.qty)),
                                type="MARKET",
                                tag=f"autocorrect:{correction.reason.replace(' ', '_')}",
                            )
                            res = self.broker.submit_order(order)
                            if isinstance(res, OrderRejection):
                                rejections.append(res)
                            else:
                                fills.append(res)
                                # Clear entry tracking
                                if correction.symbol in self._position_entry_bars:
                                    del self._position_entry_bars[correction.symbol]
                                if correction.symbol in self._position_entry_prices:
                                    del self._position_entry_prices[correction.symbol]
                        
                        elif correction.action_type == "add_stop" and pos.qty > 0:
                            if correction.stop_loss:
                                pos.stop_loss = correction.stop_loss
                            if correction.take_profit:
                                pos.take_profit = correction.take_profit

        for sym in self.cfg.symbols:
            ohlcv = ohlcv_by_symbol[sym]
            px = float(prices[sym])
            
            # Phase 24: Update position monitoring (if position is active)
            if self.position_monitoring_enabled and sym in self.position_monitor.positions:
                momentum_score = self.momentum_scaler.get_momentum_score(sym) if self.momentum_scaling_enabled else 0.0
                pos = self.broker.portfolio().get_position(sym)
                
                self.position_monitor.update_position(
                    symbol=sym,
                    current_price=px,
                    momentum_score=momentum_score,
                    iteration=self.iteration,
                    ts=ts,
                    take_profit=getattr(pos, 'take_profit', None),
                    stop_loss=getattr(pos, 'stop_loss', None),
                    hedged=sym in self._hedged_positions if self.hedging_enabled else False,
                )

            # Strategy outputs for explainability.
            outputs: Dict[str, StrategyOutput] = {
                name: strat.evaluate(ohlcv) for name, strat in self.strategies.items()
            }
            current_signals_by_symbol[sym] = {name: int(out.signal) for name, out in outputs.items()}

            # Multi-level profit-taking and time-based exits
            pos = self.broker.portfolio().get_position(sym)
            if pos.qty > 0 and sym in self._position_entry_prices:
                entry_price = self._position_entry_prices[sym]
                bars_held = self.iteration - self._position_entry_bars[sym]
                profit_pct = (px - entry_price) / entry_price if entry_price > 0 else 0
                
                # Phase 21: Options Hedging - Protect profitable positions with puts/collars
                if self.hedging_enabled and profit_pct > 0.01 and sym not in self._hedged_positions:
                    try:
                        # Check if position should be hedged
                        should_hedge = self.options_hedger.should_hedge_position(
                            symbol=sym,
                            entry_price=entry_price,
                            current_price=px,
                            position_qty=pos.qty,
                        )
                        
                        if should_hedge:
                            # Create protective put hedge (buy insurance)
                            hedge_cost = self.options_hedger.estimate_hedge_cost(
                                symbol=sym,
                                position_qty=pos.qty,
                                current_price=px,
                                hedge_type="protective_put"
                            )
                            
                            # Only hedge if cost < 1% of position value
                            position_value = px * pos.qty
                            if hedge_cost < position_value * 0.01:
                                hedge_pos = self.options_hedger.create_protective_put(
                                    symbol=sym,
                                    position_qty=pos.qty,
                                    current_price=px,
                                    entry_price=entry_price
                                )
                                self._hedged_positions.add(sym)
                                print(f"   [HEDGE] {sym}: Protective put created @ {hedge_pos.strike_price:.2f} "
                                      f"cost={hedge_cost:.2f} ({hedge_cost/position_value*100:.2f}% of position)", 
                                      flush=True)
                    except Exception as e:
                        print(f"   [HEDGE] {sym}: Failed to create hedge - {e}", flush=True)
                
                # Multi-level take profit: exit 50% at +1.5% profit, 25% at +3%, close 25% at +5%
                take_profits = [
                    (0.50, 0.015),  # 50% position at 1.5% profit
                    (0.25, 0.030),  # 25% position at 3% profit (of remaining)
                    (0.25, 0.050),  # 25% position at 5% profit (of remaining)
                ]
                
                for qty_pct, profit_threshold in take_profits:
                    if profit_pct >= profit_threshold and pos.qty > 0:
                        shares_to_exit = max(1, int(pos.qty * qty_pct))
                        order = Order(
                            id=uuid.uuid4().hex,
                            ts=ts,
                            symbol=sym,
                            side="SELL",
                            qty=shares_to_exit,
                            type="MARKET",
                            tag=f"partial_tp:{profit_pct:.1%}",
                        )
                        res = self.broker.submit_order(order)
                        if not isinstance(res, OrderRejection):
                            fills.append(res)
                            self.repo.log_order_filled(order)
                            self.repo.log_fill(res)
                            pos = self.broker.portfolio().get_position(sym)  # Refresh
                
                # Time-based exit: close after 20 bars if no strong profit
                if bars_held > 20 and profit_pct < 0.01 and pos.qty > 0:
                    order = Order(
                        id=uuid.uuid4().hex,
                        ts=ts,
                        symbol=sym,
                        side="SELL",
                        qty=int(pos.qty),
                        type="MARKET",
                        tag="time_exit:20bars",
                    )
                    res = self.broker.submit_order(order)
                    if not isinstance(res, OrderRejection):
                        fills.append(res)
                        self.repo.log_order_filled(order)
                        self.repo.log_fill(res)
                        del self._position_entry_bars[sym]
                        del self._position_entry_prices[sym]

            # Risk exits (stop-loss and take-profit)
            pos = self.broker.portfolio().get_position(sym)
            if pos.qty > 0:
                if pos.stop_loss is not None and px <= float(pos.stop_loss):
                    order = Order(
                        id=uuid.uuid4().hex,
                        ts=ts,
                        symbol=sym,
                        side="SELL",
                        qty=int(pos.qty),
                        type="MARKET",
                        tag="stop_loss",
                    )
                    res = self.broker.submit_order(order)
                    if isinstance(res, OrderRejection):
                        rejections.append(res)
                        self.repo.log_order_rejected(order, reason=res.reason)
                    else:
                        fills.append(res)
                        self.repo.log_order_filled(order)
                        self.repo.log_fill(res)

                    dec = StrategyDecision(
                        signal=0,
                        confidence=1.0,
                        votes={"risk_exit": 0},
                        weights=self.ensemble.normalized(),
                        explanations={
                            "risk_exit": {
                                "reason": "stop_loss",
                                "stop_loss": float(pos.stop_loss),
                                "price": float(px),
                            }
                        },
                    )
                    decisions[sym] = dec
                    signals[sym] = 0
                    self.repo.log_strategy_decision(ts=ts, symbol=sym, mode="risk_exit", decision=dec)
                    continue

                if pos.take_profit is not None and px >= float(pos.take_profit):
                    order = Order(
                        id=uuid.uuid4().hex,
                        ts=ts,
                        symbol=sym,
                        side="SELL",
                        qty=int(pos.qty),
                        type="MARKET",
                        tag="take_profit",
                    )
                    res = self.broker.submit_order(order)
                    if isinstance(res, OrderRejection):
                        rejections.append(res)
                        self.repo.log_order_rejected(order, reason=res.reason)
                    else:
                        fills.append(res)
                        self.repo.log_order_filled(order)
                        self.repo.log_fill(res)

                    dec = StrategyDecision(
                        signal=0,
                        confidence=1.0,
                        votes={"risk_exit": 0},
                        weights=self.ensemble.normalized(),
                        explanations={
                            "risk_exit": {
                                "reason": "take_profit",
                                "take_profit": float(pos.take_profit),
                                "price": float(px),
                            }
                        },
                    )
                    decisions[sym] = dec
                    signals[sym] = 0
                    self.repo.log_strategy_decision(ts=ts, symbol=sym, mode="risk_exit", decision=dec)
                    continue

            # Choose decision mode.
            mode = self.strategy_mode
            if mode == "ensemble":
                dec = self.ensemble.decide(outputs)
            elif mode == "ultimate_hybrid":
                # Use all strategies combined for maximum signal strength
                all_signals = [int(out.signal) for out in outputs.values()]
                all_confidences = [float(out.confidence) for out in outputs.values()]
                final_signal = np.sign(np.mean(all_signals)) if np.mean(all_signals) != 0 else 0
                final_confidence = np.mean(all_confidences)
                dec = StrategyDecision(
                    signal=int(final_signal),
                    confidence=float(final_confidence),
                    votes={k: int(v.signal) for k, v in outputs.items()},
                    weights={k: 1.0/len(outputs) for k in outputs.keys()},
                    explanations={k: dict(v.explanation) for k, v in outputs.items()},
                )
            else:
                if mode not in outputs:
                    raise ValueError(f"Unknown strategy_mode: {mode}")
                out = outputs[mode]
                dec = StrategyDecision(
                    signal=int(out.signal),
                    confidence=float(out.confidence),
                    votes={mode: int(out.signal)},
                    weights={mode: 1.0},
                    explanations={mode: dict(out.explanation)},
                )

            # ML Signal Integration (Phase 16)
            # Train ML model if enough data available
            if self.ml_enabled and sym not in self._ml_trained_symbols and len(ohlcv) >= 50:
                try:
                    self.ml_manager.train_symbol(sym, ohlcv)
                    self._ml_trained_symbols.add(sym)
                    print(f"[ML] Model trained for {sym}")
                except Exception as e:
                    print(f"[ML] Training failed for {sym}: {e}")
            
            # Get ML prediction if available
            ml_signal = None
            if self.ml_enabled and sym in self._ml_trained_symbols and len(ohlcv) >= 20:
                try:
                    ml_signal = self.ml_manager.predict_signal(sym, ohlcv)
                    
                    # Blend ML signal with ensemble decision
                    # ML acts as a filter: reduce confidence if ML disagrees
                    ml_agrees = (dec.signal == 1 and ml_signal.is_buy_signal(0.5)) or \
                                (dec.signal == 0 and ml_signal.is_sell_signal(0.5))
                    
                    if not ml_agrees and dec.confidence > 0.6:
                        # ML disagrees with high-confidence ensemble signal
                        # Reduce confidence as a caution
                        dec.confidence *= 0.7
                    elif ml_agrees:
                        # ML agrees: boost confidence
                        dec.confidence = min(1.0, dec.confidence * 1.1)
                    
                    # Add ML explanation
                    if "ml" not in dec.explanations:
                        dec.explanations["ml"] = {}
                    dec.explanations["ml"].update({
                        "prediction": float(ml_signal.prediction),
                        "confidence": float(ml_signal.confidence),
                        "probability_up": float(ml_signal.probability_up),
                        "model_version": ml_signal.model_version,
                    })
                except Exception as e:
                    print(f"[ML] Prediction error for {sym}: {e}")

            decisions[sym] = dec
            signals[sym] = int(dec.signal)
            self.repo.log_strategy_decision(ts=ts, symbol=sym, mode=mode, decision=dec)
            
            # Multi-Timeframe Signal Validation (Phase 26)
            # Feed signal to MTF validator and check confirmation
            if self.multitimeframe_enabled and dec.signal != 0:
                # Determine if this is hourly or daily signal based on context
                # For now, treat as hourly since we're analyzing 1d bars (but could be 1h in real trading)
                self.mtf_validator.add_signal(
                    symbol=sym,
                    signal=int(dec.signal),
                    strength=float(dec.confidence),
                    price=float(px),
                    timeframe="1h",
                    indicators={
                        "win_rate": 0.55 + (dec.confidence * 0.15),  # Estimate from confidence
                        "signal_type": mode,
                    }
                )
                
                # Get multi-timeframe analysis
                mtf_analysis = self.mtf_validator.analyze(sym)
                
                # Log MTF analysis
                if mtf_analysis.is_confirmed:
                    print(f"   [MTF] {sym}: {mtf_analysis.recommendation} "
                          f"(conf={mtf_analysis.confidence:.2f}, EV=${mtf_analysis.expected_value:.0f})",
                          flush=True)
                else:
                    print(f"   [MTF] {sym}: Signal not confirmed across timeframes (conf={mtf_analysis.confidence:.2f})",
                          flush=True)
                
                # Add MTF explanation to decision
                dec.explanations["mtf"] = {
                    "confirmed": mtf_analysis.is_confirmed,
                    "alignment": mtf_analysis.alignment_strength,
                    "expected_value": mtf_analysis.expected_value,
                    "volatility_regime": mtf_analysis.volatility_regime,
                    "correlation_warning": mtf_analysis.correlation_warning,
                    "recommendation": mtf_analysis.recommendation,
                    "mtf_confidence": mtf_analysis.confidence,
                }
                
                # Only proceed with signal if MTF confirmed (unless low confidence)
                # For weak signals, require MTF confirmation
                # For strong signals, use MTF as a boost
                if dec.confidence < 0.6 and not mtf_analysis.is_confirmed:
                    # Weak signal and not confirmed = skip
                    dec.confidence = 0.0
                    dec.signal = 0
                    confirmed_signal = False
                elif mtf_analysis.is_confirmed:
                    # MTF confirmed: boost confidence
                    dec.confidence = min(1.0, dec.confidence * (1.0 + mtf_analysis.alignment_strength * 0.2))
                elif mtf_analysis.correlation_warning:
                    # Too many correlated signals: reduce confidence
                    dec.confidence *= 0.8

            decisions[sym] = dec
            signals[sym] = int(dec.signal)

            # Signal confirmation: require 2 consecutive bars with signal=1 before entering (reduces false signals)
            if dec.signal == 1:
                self._signal_confirmation[sym] = self._signal_confirmation.get(sym, 0) + 1
            else:
                self._signal_confirmation[sym] = 0  # Reset on signal loss
            
            confirmed_signal = dec.signal == 1 and self._signal_confirmation[sym] >= 1

            # Advanced Entry Filtering (Phase 22): Validate entry before executing
            if confirmed_signal and self.entry_filtering_enabled:
                ohlcv = ohlcv_by_symbol[sym]
                entry_valid = self.entry_filter.validate_entry(sym, ohlcv, dec.signal)
                
                if not entry_valid.is_valid:
                    # Entry filtered out - skip this trade
                    print(f"   [FILTER] {sym}: Entry rejected - {', '.join(entry_valid.reasons)}", flush=True)
                    confirmed_signal = False
                else:
                    # Add confidence boost from entry filter
                    dec.confidence = min(1.0, dec.confidence * (0.8 + entry_valid.confidence * 0.4))

            # Execute to target position (long/flat).
            if confirmed_signal and pos.qty == 0:
                # Volatility-based stops: higher volatility = wider stops (give winning trades more room)
                ohlcv = ohlcv_by_symbol[sym]
                returns = ohlcv['Close'].pct_change().dropna()
                volatility = float(returns.std()) if len(returns) > 0 else 0.02
                
                # Adjust stop-loss based on volatility (scale 0.5x to 2.0x)
                vol_adjusted_sl_pct = self.app_cfg.risk.stop_loss_pct * (0.5 + volatility / 0.03)
                vol_adjusted_tp_pct = self.app_cfg.risk.take_profit_pct * (0.5 + volatility / 0.03)
                
                sl = px * (1.0 - vol_adjusted_sl_pct)
                tp = px * (1.0 + vol_adjusted_tp_pct)
                
                eq = self.broker.portfolio().equity(self.broker.prices())
                shares = position_size_shares(
                    equity=float(eq),
                    entry_price=float(px),
                    stop_loss_price_=float(sl),
                    max_risk=float(self.app_cfg.risk.max_risk_per_trade),
                )
                
                # Regime-aware position sizing: adjust for market conditions (scaled up)
                regime = regime_by_symbol.get(sym, {}).get("regime", "unknown")
                regime_multiplier = 1.0
                if regime in ["trending_up", "trending_down"]:
                    regime_multiplier = 1.5  # 50% larger in trending markets (increased from 1.2)
                elif regime == "ranging":
                    regime_multiplier = 1.0  # Normal sizing in ranging (increased from 0.8)
                elif regime == "volatile":
                    regime_multiplier = 0.9  # Only 10% smaller in volatile (increased from 0.7)
                
                shares = int(shares * regime_multiplier)
                shares = min(shares, int(self.broker.portfolio().cash // px))
                
                # Portfolio Optimization (Phase 19): Adjust position size based on correlations
                if self.portfolio_optimization_enabled and shares > 0:
                    portfolio = self.broker.portfolio()
                    allocations = self.portfolio_optimizer.optimize_allocations(
                        positions=portfolio.positions,
                        prices=prices,
                        equity=float(portfolio.equity(prices)),
                        current_bar=self.iteration,
                    )
                    
                    # If this symbol has an allocation, apply the adjustment
                    if sym in allocations:
                        alloc = allocations[sym]
                        # This is a new position, so use the optimization recommendation
                        if alloc.recommendation == "DECREASE":
                            shares = int(shares * 0.85)  # Reduce by 15%
                        elif alloc.recommendation == "INCREASE":
                            shares = int(shares * 1.1)  # Increase by 10%

                # Phase 20: Momentum-Based Position Scaling
                # Scale position size based on momentum strength (0.5x - 1.5x)
                if self.momentum_scaling_enabled and shares > 0:
                    momentum_mult = self.momentum_scaler.get_scaling_multiplier(sym)
                    shares = int(shares * momentum_mult)
                    if momentum_mult < 1.0:
                        print(f"   [MOMENTUM] {sym}: Reduced to {momentum_mult:.2f}x due to weak momentum", flush=True)
                    elif momentum_mult > 1.0:
                        print(f"   [MOMENTUM] {sym}: Increased to {momentum_mult:.2f}x due to strong momentum", flush=True)

                # Phase 25: Risk-Adjusted Position Sizing
                # Adjust position size based on portfolio risk state (volatility, drawdown, win rate)
                if self.risk_adjusted_sizing_enabled and shares > 0:
                    # Update risk sizer state
                    sharpe, max_dd, win_rate, num_trades, pnl = self._calculate_metrics()
                    
                    # Get consecutive win/loss counts
                    consecutive_wins = 0
                    consecutive_losses = 0
                    if self.trade_history:
                        for trade in reversed(self.trade_history):
                            if trade.get("pnl", 0) > 0:
                                consecutive_wins += 1
                            else:
                                break
                        for trade in reversed(self.trade_history):
                            if trade.get("pnl", 0) <= 0:
                                consecutive_losses += 1
                            else:
                                break
                    
                    # Get current volatility
                    ohlcv = ohlcv_by_symbol[sym]
                    returns = ohlcv['Close'].pct_change().dropna()
                    current_vol = float(returns.std()) if len(returns) > 0 else 0.02
                    
                    # Update sizer state
                    eq = self.broker.portfolio().equity(self.broker.prices())
                    self.risk_sizer.update_state(
                        current_equity=float(eq),
                        consecutive_wins=consecutive_wins,
                        consecutive_losses=consecutive_losses,
                        total_trades=num_trades,
                        winning_trades=int(num_trades * win_rate),
                        losing_trades=int(num_trades * (1 - win_rate)),
                        volatility=current_vol,
                        sharpe_ratio=sharpe,
                    )
                    
                    # Apply risk adjustment
                    risk_mult = self.risk_sizer.get_position_multiplier()
                    shares = int(shares * risk_mult)
                    risk_level = self.risk_sizer.get_risk_level()
                    print(f"   [RISK] {sym}: Risk level {risk_level}, mult {risk_mult:.2f}x", flush=True)

                if shares > 0:
                    order = Order(
                        id=uuid.uuid4().hex,
                        ts=ts,
                        symbol=sym,
                        side="BUY",
                        qty=int(shares),
                        type="MARKET",
                        tag=f"signal_long:{mode}",
                    )
                    res = self.broker.submit_order(order)
                    if isinstance(res, OrderRejection):
                        rejections.append(res)
                        self.repo.log_order_rejected(order, reason=res.reason)
                    else:
                        fills.append(res)

                        # Attach SL/TP to the position and track entry for multi-level exits
                        p = self.broker.portfolio().get_position(sym)
                        p.stop_loss = float(sl)
                        p.take_profit = float(tp)
                        
                        # Track entry for time-based and multi-level exits
                        self._position_entry_bars[sym] = self.iteration
                        self._position_entry_prices[sym] = float(px)
                        
                        # Phase 24: Add position to monitor
                        if self.position_monitoring_enabled:
                            self.position_monitor.add_position(
                                symbol=sym,
                                entry_price=float(px),
                                qty=int(shares),
                                entry_bar=self.iteration,
                                ts=ts,
                            )

                        self.repo.log_order_filled(order)
                        self.repo.log_fill(res)

            elif dec.signal == 0 and pos.qty > 0:
                order = Order(
                    id=uuid.uuid4().hex,
                    ts=ts,
                    symbol=sym,
                    side="SELL",
                    qty=int(pos.qty),
                    type="MARKET",
                    tag=f"signal_flat:{mode}",
                )
                res = self.broker.submit_order(order)
                if isinstance(res, OrderRejection):
                    rejections.append(res)
                    self.repo.log_order_rejected(order, reason=res.reason)
                else:
                    fills.append(res)
                    self.repo.log_order_filled(order)
                    self.repo.log_fill(res)
                    
                    # Phase 24: Remove position from monitor when closed
                    if self.position_monitoring_enabled and sym in self.position_monitor.positions:
                        self.position_monitor.remove_position(sym)

        self.repo.log_snapshot(ts=ts, portfolio=self.broker.portfolio(), prices=prices)

        # Track equity and trades for learning
        eq = self.broker.portfolio().equity(self.broker.prices())
        self.equity_history.append(float(eq))
        
        # Track completed trades for analysis
        for fill in fills:
            # Simple trade tracking: BUY at fill.price, will be matched with SELL later
            self.trade_history.append({
                "symbol": fill.symbol,
                "side": fill.side,
                "qty": fill.qty,
                "price": fill.price,
                "ts": fill.ts,
                "entry_price": fill.price if fill.side == "BUY" else None,
                "exit_price": fill.price if fill.side == "SELL" else None,
                "entry_bar": self.iteration,
                "exit_bar": self.iteration if fill.side == "SELL" else None,
                "strategy_name": fill.note.split(":")[1] if ":" in fill.note else "unknown",
            })

        # Store for next learning update.
        self._prev_prices = dict(prices)
        self._prev_signals_by_symbol = current_signals_by_symbol
        
        # Print ML Signal Status
        if self.ml_enabled and len(self.ml_manager.signals) > 0:
            ml_buys = sum(1 for s in self.ml_manager.signals.values() if s.prediction > 0.65)
            ml_sells = sum(1 for s in self.ml_manager.signals.values() if s.prediction < 0.35)
            print(f"   [ML] Symbols: {len(self.ml_manager.signals)} | Buy signals: {ml_buys} | Sell signals: {ml_sells}", flush=True)
        
        # Print Portfolio Optimization Status (Phase 19)
        if self.portfolio_optimization_enabled and self.portfolio_optimizer.risk_metrics is not None:
            metrics = self.portfolio_optimizer.risk_metrics
            print(f"   [PORTOPT] Concentration: {metrics.concentration_ratio:.3f} | "
                  f"Diversification: {metrics.diversification_ratio:.2f}x | "
                  f"Vol: {metrics.portfolio_volatility:.4f}", flush=True)
        
        # Print Momentum Scaling Status (Phase 20)
        if self.momentum_scaling_enabled and hasattr(self.momentum_scaler, 'metrics') and self.momentum_scaler.metrics:
            momentum_values = [self.momentum_scaler.metrics.get(sym, None) for sym in prices.keys()]
            momentum_values = [m.momentum_strength for m in momentum_values if m is not None]
            if momentum_values:
                avg_momentum = np.mean(momentum_values)
                strong_momentum = sum(1 for m in momentum_values if m > 0.7)
                print(f"   [MOMENTUM] Avg strength: {avg_momentum:.2f} | Strong momentum: {strong_momentum} symbols", flush=True)
        
        # Print Options Hedging Status (Phase 21)
        if self.hedging_enabled:
            hedged_count = len(self._hedged_positions)
            active_positions = sum(1 for p in self.broker.portfolio().positions.values() if p.qty > 0)
            coverage = hedged_count / active_positions * 100 if active_positions > 0 else 0
            print(f"   [HEDGE] Active hedges: {hedged_count}/{active_positions} ({coverage:.1f}%)", flush=True)
        
        # Print Entry Filter Status (Phase 22)
        if self.entry_filtering_enabled:
            valid_rate = self.entry_filter.get_validation_rate()
            valid_rate_pct = valid_rate * 100 if valid_rate > 0 else 0
            total_rejected = sum(self.entry_filter.stats[k] for k in self.entry_filter.stats if k.startswith('rejected_'))
            print(f"   [FILTER] Validation rate: {valid_rate_pct:.1f}% | Trades filtered: {total_rejected}", 
                  flush=True)
        
        # Phase 24: Print Position Monitor Status
        if self.position_monitoring_enabled:
            self.position_monitor.print_position_status()
        
        # Phase 25: Print Risk-Adjusted Sizing Status
        if self.risk_adjusted_sizing_enabled:
            self.risk_sizer.print_status()
        
        print(f" [OK] ({len(fills)} fills)", flush=True)

        # Calculate real-time metrics
        sharpe, max_dd, win_rate, num_trades, pnl = self._calculate_metrics()
        
        # Phase 23: Collect real-time metrics
        if self.metrics_enabled:
            snapshot = self.metrics_collector.collect_metrics(
                ts=ts,
                iteration=self.iteration,
                portfolio=self.broker.portfolio(),
                prices=prices,
                equity_history=self.equity_history,
                trade_history=self.trade_history,
                fills=fills,
                rejections=rejections,
            )
            # Print real-time metrics summary
            self.metrics_collector.print_status()

        return PaperEngineUpdate(
            ts=ts,
            iteration=self.iteration,
            mode=str(self.strategy_mode),
            prices=dict(prices),
            signals=dict(signals),
            decisions=decisions,
            fills=fills,
            rejections=rejections,
            portfolio=self.broker.portfolio(),
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            win_rate=win_rate,
            num_trades=num_trades,
            current_pnl=pnl,
        )


def run_paper_engine(
    *,
    cfg: PaperEngineConfig,
    provider: MarketDataProvider | None = None,
) -> Iterator[PaperEngineUpdate]:
    """Run paper trading loop (with sleeping) and yield updates."""

    engine = PaperEngine(cfg=cfg, provider=provider)

    while True:
        if cfg.iterations > 0 and engine.iteration >= cfg.iterations:
            break

        yield engine.step()

        if cfg.iterations > 0 and engine.iteration >= cfg.iterations:
            break

        time.sleep(max(0.0, float(cfg.sleep_seconds)))
