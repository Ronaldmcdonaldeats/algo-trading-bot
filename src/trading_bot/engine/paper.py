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
from trading_bot.config import load_config
from trading_bot.core.models import Fill, Order, Portfolio
from trading_bot.data.providers import MarketDataProvider, MockDataProvider
from trading_bot.db.repository import SqliteRepository
from trading_bot.learn.adaptive_controller import AdaptiveLearningController
from trading_bot.learn.ensemble import ExponentialWeightsEnsemble, reward_to_unit_interval
from trading_bot.learn.tuner import default_params, maybe_tune_weekly
from trading_bot.risk import position_size_shares, stop_loss_price, take_profit_price
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.base import StrategyDecision, StrategyOutput
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy


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

    # Phase 3
    strategy_mode: str = "ensemble"  # ensemble|mean_reversion_rsi|momentum_macd_volume|breakout_atr
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
        print(" ✓", flush=True)

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

        for sym in self.cfg.symbols:
            ohlcv = ohlcv_by_symbol[sym]
            px = float(prices[sym])

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

            decisions[sym] = dec
            signals[sym] = int(dec.signal)
            self.repo.log_strategy_decision(ts=ts, symbol=sym, mode=mode, decision=dec)

            # Signal confirmation: require 2 consecutive bars with signal=1 before entering (reduces false signals)
            if dec.signal == 1:
                self._signal_confirmation[sym] = self._signal_confirmation.get(sym, 0) + 1
            else:
                self._signal_confirmation[sym] = 0  # Reset on signal loss
            
            confirmed_signal = dec.signal == 1 and self._signal_confirmation[sym] >= 2

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
                
                # Regime-aware position sizing: adjust for market conditions
                regime = regime_by_symbol.get(sym, {}).get("regime", "unknown")
                regime_multiplier = 1.0
                if regime in ["trending_up", "trending_down"]:
                    regime_multiplier = 1.2  # 20% larger in trending markets
                elif regime == "ranging":
                    regime_multiplier = 0.8  # 20% smaller in ranging (chop)
                elif regime == "volatile":
                    regime_multiplier = 0.7  # 30% smaller in volatile (protect capital)
                
                shares = int(shares * regime_multiplier)
                shares = min(shares, int(self.broker.portfolio().cash // px))

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
        
        print(f" ✓ ({len(fills)} fills)", flush=True)

        # Calculate real-time metrics
        sharpe, max_dd, win_rate, num_trades, pnl = self._calculate_metrics()

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
