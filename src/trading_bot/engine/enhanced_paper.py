"""Enhanced Paper Trading Engine with Portfolio Management & Monitoring

This integrates the Phase 2 portfolio management, analytics, and monitoring modules
into the trading engine for real-time P&L tracking, risk monitoring, and performance analysis.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from trading_bot.broker.base import OrderRejection
from trading_bot.broker.paper import PaperBroker, PaperBrokerConfig
from trading_bot.configs import load_config
from trading_bot.core.models import Fill, Order, Portfolio
from trading_bot.data.providers import MarketDataProvider, AlpacaProvider, MockDataProvider
from trading_bot.db.repository import SqliteRepository
from trading_bot.learn.adaptive_controller import AdaptiveLearningController
from trading_bot.learn.ensemble import ExponentialWeightsEnsemble, reward_to_unit_interval
from trading_bot.learn.tuner import default_params, maybe_tune_weekly
from trading_bot.risk import position_size_shares, stop_loss_price, take_profit_price
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.base import StrategyDecision, StrategyOutput
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy

# NEW: Portfolio management modules
from trading_bot.portfolio import PortfolioManager, PerformanceAnalytics
from trading_bot.analytics import DataValidator
from trading_bot.monitor import AlertSystem, CircuitBreaker, AlertLevel, AlertType


@dataclass(frozen=True)
class EnhancedPaperEngineConfig:
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
    strategy_mode: str = "ensemble"
    enable_learning: bool = True
    tune_weekly: bool = True
    learning_eta: float = 0.3
    ignore_market_hours: bool = False
    memory_mode: bool = False
    
    # Phase 2 integration (NEW)
    enable_portfolio_mgmt: bool = True  # Use PortfolioManager for tracking
    enable_risk_monitoring: bool = True  # Use CircuitBreaker for risk control
    enable_data_validation: bool = True  # Validate market data quality
    max_portfolio_loss_pct: float = 0.05  # Circuit breaker: -5% cumulative
    max_intraday_loss_pct: float = 0.02  # Circuit breaker: -2% intraday
    max_position_loss_pct: float = 0.10  # Circuit breaker: -10% per position


@dataclass(frozen=True)
class EnhancedPaperEngineUpdate:
    """Enhanced update with portfolio and risk metrics"""
    ts: datetime
    iteration: int
    mode: str
    prices: dict[str, float]
    signals: dict[str, int]
    decisions: dict[str, StrategyDecision]
    fills: list[Fill]
    rejections: list[OrderRejection]
    portfolio: Portfolio
    
    # Real-time performance metrics (from Phase 1)
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    current_pnl: float = 0.0
    
    # NEW: Portfolio management metrics (Phase 2)
    portfolio_value: float = 0.0
    invested_value: float = 0.0
    cash: float = 0.0
    leverage: float = 0.0
    utilization_pct: float = 0.0
    num_open_positions: int = 0
    sector_exposure: dict = None
    
    # NEW: Risk monitoring (Phase 2)
    circuit_breaker_triggered: bool = False
    circuit_breaker_reason: str = ""
    data_quality_issues: int = 0
    critical_alerts: int = 0


def _normalize_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalize OHLCV data from market data provider"""
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

    # Convert to float32 to reduce memory
    for col in ['Open', 'High', 'Low', 'Close']:
        if col in out.columns and out[col].dtype != np.float32:
            out[col] = out[col].astype(np.float32)
    if 'Volume' in out.columns and out['Volume'].dtype not in [np.uint32, np.uint64]:
        out['Volume'] = out['Volume'].astype(np.uint32)

    return out


class EnhancedPaperEngine:
    """Paper trading engine with integrated portfolio management & monitoring"""
    
    def __init__(
        self,
        *,
        cfg: EnhancedPaperEngineConfig,
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

        # Phase 1 learning components
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

        self.params: Dict[str, Dict[str, Any]] = default_params()
        for k, v in persisted_params.items():
            if isinstance(v, dict):
                self.params[k] = dict(v)

        self.strategies = self._build_strategies(self.params)

        names = list(self.strategies.keys())
        if persisted_weights:
            weights = {n: float(persisted_weights.get(n, 1.0)) for n in names}
        else:
            weights = {n: 1.0 for n in names}

        self.ensemble = ExponentialWeightsEnsemble(weights=weights, eta=float(cfg.learning_eta))
        self.adaptive_controller = AdaptiveLearningController(
            ensemble=self.ensemble,
            min_trades_for_analysis=5,
        )
        
        self.trade_history: list[dict] = []
        self.equity_history: list[float] = [float(cfg.start_cash)]
        self._prev_prices: Optional[Dict[str, float]] = None
        self._prev_signals_by_symbol: Dict[str, Dict[str, int]] = {}
        self._signal_confirmation: Dict[str, int] = {}
        self._position_entry_bars: Dict[str, int] = {}
        self._position_entry_prices: Dict[str, float] = {}

        # NEW: Phase 2 portfolio management integration
        self.portfolio_mgr = PortfolioManager(float(cfg.start_cash)) if cfg.enable_portfolio_mgmt else None
        self.performance_analytics = PerformanceAnalytics(self.portfolio_mgr) if cfg.enable_portfolio_mgmt else None
        self.data_validator = DataValidator() if cfg.enable_data_validation else None
        self.alert_system = AlertSystem() if cfg.enable_risk_monitoring else None
        self.circuit_breaker = CircuitBreaker(
            self.alert_system,
            max_loss_pct=cfg.max_portfolio_loss_pct,
            max_intraday_loss_pct=cfg.max_intraday_loss_pct,
            max_position_loss_pct=cfg.max_position_loss_pct
        ) if cfg.enable_risk_monitoring else None
        
        # Register alert handlers
        if self.alert_system:
            self.alert_system.register_handler(AlertLevel.CRITICAL, self._handle_critical_alert)
            self.alert_system.register_handler(AlertLevel.WARNING, self._handle_warning_alert)
        
        self._data_quality_issues = 0
        self._critical_alerts = 0

    def _build_strategies(self, params: Dict[str, Dict[str, Any]]) -> Dict[str, StrategyOutput | Any]:
        """Build strategy instances from parameters"""
        strategies = {}

        rsi_params = params.get("mean_reversion_rsi", {})
        strategies["mean_reversion_rsi"] = RsiMeanReversionStrategy(
            rsi_period=int(rsi_params.get("rsi_period", 14)),
            entry_oversold=float(rsi_params.get("entry_oversold", 30.0)),
            exit_rsi=float(rsi_params.get("exit_rsi", 50.0)),
        )

        macd_params = params.get("momentum_macd_volume", {})
        strategies["momentum_macd_volume"] = MacdVolumeMomentumStrategy(
            macd_fast=int(macd_params.get("macd_fast", 12)),
            macd_slow=int(macd_params.get("macd_slow", 26)),
            macd_signal=int(macd_params.get("macd_signal", 9)),
            vol_sma=int(macd_params.get("vol_sma", 20)),
            vol_mult=float(macd_params.get("vol_mult", 1.0)),
        )

        atr_params = params.get("breakout_atr", {})
        strategies["breakout_atr"] = AtrBreakoutStrategy(
            atr_period=int(atr_params.get("atr_period", 14)),
            breakout_lookback=int(atr_params.get("breakout_lookback", 20)),
            atr_mult=float(atr_params.get("atr_mult", 1.0)),
        )

        return strategies

    def _validate_market_data(self, ohlcv_by_symbol: Dict[str, pd.DataFrame]) -> int:
        """Validate market data quality using DataValidator
        
        Returns: Number of data quality issues found
        """
        if not self.data_validator:
            return 0
        
        self.data_validator.clear()
        issue_count = 0
        
        for symbol, df in ohlcv_by_symbol.items():
            issues = self.data_validator.validate_ohlcv(df, symbol)
            issue_count += len(issues)
            
            # Log critical issues
            for issue in issues:
                if issue.severity == "error":
                    self.alert_system.create_alert(
                        AlertType.EXECUTION,
                        AlertLevel.CRITICAL,
                        symbol,
                        f"Data quality error: {issue.details}"
                    )
                elif issue.severity == "warning":
                    self.alert_system.create_alert(
                        AlertType.EXECUTION,
                        AlertLevel.WARNING,
                        symbol,
                        f"Data quality warning: {issue.details}"
                    )
        
        return issue_count

    def _update_portfolio_from_broker(self, prices: Dict[str, float]) -> None:
        """Sync portfolio manager with broker positions"""
        if not self.portfolio_mgr:
            return
        
        broker_portfolio = self.broker.portfolio()
        
        # Update prices
        self.portfolio_mgr.update_prices(prices)
        
        # Sync positions (would need more sophisticated tracking in production)
        # For now, just update cash from broker
        self.portfolio_mgr.cash = broker_portfolio.cash

    def _check_risk_limits(self, prices: Dict[str, float]) -> Tuple[bool, str]:
        """Check portfolio risk limits and trigger circuit breaker if needed
        
        Returns: (triggered, reason)
        """
        if not self.circuit_breaker or not self.portfolio_mgr:
            return False, ""
        
        start_capital = self.cfg.start_cash
        current_value = self.portfolio_mgr.total_value
        cumulative_loss_pct = (current_value - start_capital) / start_capital
        
        # Calculate intraday loss from peak
        peak_value = max(self.equity_history) if self.equity_history else start_capital
        intraday_loss_pct = (current_value - peak_value) / peak_value if peak_value > 0 else 0
        
        # Get position losses
        position_losses = {}
        for symbol, pos in self.portfolio_mgr.positions.items():
            if pos.current_price > 0 and pos.entry_price > 0:
                loss = (pos.current_price - pos.entry_price) / pos.entry_price
                position_losses[symbol] = loss
        
        # Check circuit breaker
        triggered = self.circuit_breaker.check_circuit_breaker(
            portfolio_value=current_value,
            current_loss_pct=cumulative_loss_pct,
            position_losses=position_losses
        )
        
        reason = self.circuit_breaker.trigger_reason if triggered else ""
        return triggered, reason

    def _handle_critical_alert(self, alert) -> None:
        """Handle critical alerts"""
        self._critical_alerts += 1
        print(f"[CRITICAL ALERT] {alert.symbol}: {alert.message}")

    def _handle_warning_alert(self, alert) -> None:
        """Handle warning alerts"""
        print(f"[WARNING] {alert.symbol}: {alert.message}")

    def _calculate_metrics(self) -> Tuple[float, float, float, int, float]:
        """Calculate performance metrics using PerformanceAnalytics if available
        
        Returns: (sharpe_ratio, max_drawdown_pct, win_rate, num_trades, current_pnl)
        """
        if self.performance_analytics and self.portfolio_mgr:
            try:
                sharpe = self.performance_analytics.calculate_sharpe_ratio()
                max_dd = self.performance_analytics.calculate_max_drawdown() * 100
                win_rate = self.performance_analytics.calculate_win_rate() / 100
                summary = self.performance_analytics.get_performance_summary()
                num_trades = summary.get("total_trades", 0)
                current_pnl = self.portfolio_mgr.total_value - self.cfg.start_cash
                return sharpe, max_dd, win_rate, num_trades, current_pnl
            except Exception as e:
                print(f"Error calculating metrics: {e}")
        
        # Fallback to previous implementation
        if len(self.equity_history) < 2:
            sharpe = 0.0
        else:
            returns = np.diff(self.equity_history) / np.array(self.equity_history[:-1])
            excess_returns = returns - (0.02 / 252)
            sharpe = float(np.sqrt(252) * np.mean(excess_returns) / (np.std(excess_returns) + 1e-8))
        
        if len(self.equity_history) < 2:
            max_dd = 0.0
        else:
            cummax = np.maximum.accumulate(self.equity_history)
            drawdown = (np.array(self.equity_history) - cummax) / cummax
            max_dd = float(np.min(drawdown)) * 100
        
        if len(self.trade_history) == 0:
            win_rate = 0.0
            num_trades = 0
        else:
            winning = len([t for t in self.trade_history if t.get("pnl", 0) > 0])
            num_trades = len(self.trade_history)
            win_rate = winning / num_trades if num_trades > 0 else 0.0
        
        start_cash = float(self.cfg.start_cash)
        current_equity = self.equity_history[-1] if self.equity_history else start_cash
        current_pnl = current_equity - start_cash
        
        return sharpe, max_dd, win_rate, num_trades, current_pnl

    def step(self, *, now: datetime | None = None) -> EnhancedPaperEngineUpdate:
        """Execute one trading step with integrated portfolio management and risk monitoring"""
        self.iteration += 1
        ts = now or datetime.utcnow()

        print(f"[{self.iteration}] Fetching data for {len(self.cfg.symbols)} symbols...", end="", flush=True)
        bars = self.data.download_bars(
            symbols=self.cfg.symbols,
            period=self.cfg.period,
            interval=self.cfg.interval,
        )
        print(" [OK]", flush=True)

        # Normalize and validate data
        ohlcv_by_symbol: Dict[str, pd.DataFrame] = {}
        prices: Dict[str, float] = {}
        batch_size = 10 if self.cfg.memory_mode else 20
        
        print(f"[{self.iteration}] Validating data quality...", end="", flush=True)
        for i in range(0, len(self.cfg.symbols), batch_size):
            batch = self.cfg.symbols[i:i + batch_size]
            for sym in batch:
                ohlcv = _normalize_ohlcv(bars, sym)
                ohlcv_by_symbol[sym] = ohlcv
                px = float(ohlcv["Close"].iloc[-1])
                prices[sym] = px
                self.broker.set_price(sym, px)
        
        # NEW: Validate data quality
        data_quality_issues = self._validate_market_data(ohlcv_by_symbol) if self.cfg.enable_data_validation else 0
        self._data_quality_issues = data_quality_issues
        print(" [OK]", flush=True)

        print(f"[{self.iteration}] Processing {len(ohlcv_by_symbol)} symbols...", end="", flush=True)

        # Learning update (existing)
        if self.enable_learning and self._prev_prices is not None and self._prev_signals_by_symbol:
            rewards_sum = {name: 0.0 for name in self.strategies.keys()}
            n = 0
            for sym, prev_px in self._prev_prices.items():
                if sym not in prices or prev_px <= 0:
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

        # Weekly tuning (existing)
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
                for name in self.strategies.keys():
                    self.ensemble.weights.setdefault(name, 1.0)
                self.last_tuned_bucket = tune.note.split("tuned_week=", 1)[1].strip()
                self.repo.log_learning_state(
                    ts=ts,
                    weights=self.ensemble.normalized(),
                    params=self.params,
                    note=tune.note,
                )

        # Adaptive learning (existing)
        if self.enable_learning:
            equity_series = pd.Series(self.equity_history) if self.equity_history else None
            adaptive_decision = self.adaptive_controller.step(
                ohlcv_by_symbol=ohlcv_by_symbol,
                current_params=self.params,
                trades=self.trade_history,
                equity_series=equity_series,
                now=ts,
            )
            
            for name, adjusted_w in adaptive_decision.adjusted_weights.items():
                current_w = self.ensemble.weights.get(name, 1.0)
                blended = 0.7 * current_w + 0.3 * adjusted_w
                self.ensemble.weights[name] = float(max(self.ensemble.min_weight, blended))
            
            self.repo.log_adaptive_decision(
                ts=ts,
                regime=adaptive_decision.regime.value,
                regime_confidence=adaptive_decision.regime_confidence,
                adjusted_weights=adaptive_decision.adjusted_weights,
                param_recommendations=adaptive_decision.parameter_recommendations,
                anomalies=adaptive_decision.anomalies,
                explanation=adaptive_decision.explanation,
            )

        # NEW: Update portfolio manager with current prices
        if self.cfg.enable_portfolio_mgmt:
            self._update_portfolio_from_broker(prices)
            self.portfolio_mgr.take_snapshot()

        # NEW: Check risk limits and circuit breaker
        circuit_triggered = False
        circuit_reason = ""
        if self.cfg.enable_risk_monitoring:
            circuit_triggered, circuit_reason = self._check_risk_limits(prices)
            if circuit_triggered:
                print(f"[{self.iteration}] CIRCUIT BREAKER TRIGGERED: {circuit_reason}")

        # Trading logic (continue existing implementation)
        decisions: Dict[str, StrategyDecision] = {}
        signals: Dict[str, int] = {}
        fills: list[Fill] = []
        rejections: list[OrderRejection] = []
        current_signals_by_symbol: Dict[str, Dict[str, int]] = {}

        # Don't execute trades if circuit breaker is triggered
        if circuit_triggered:
            print(f"[{self.iteration}] Trades halted due to circuit breaker")
            # Continue with rest of step but don't open new positions
        
        for sym in self.cfg.symbols:
            if circuit_triggered:
                # Only allow exits, not entries
                ohlcv = ohlcv_by_symbol[sym]
                px = float(prices[sym])
                pos = self.broker.portfolio().get_position(sym)
                
                if pos.qty > 0:
                    # Close any open positions
                    order = Order(
                        id=uuid.uuid4().hex,
                        ts=ts,
                        symbol=sym,
                        side="SELL",
                        qty=int(pos.qty),
                        type="MARKET",
                        tag="circuit_breaker_exit",
                    )
                    res = self.broker.submit_order(order)
                    if not isinstance(res, OrderRejection):
                        fills.append(res)
                        self.repo.log_order_filled(order)
                        self.repo.log_fill(res)
                continue
            
            # Normal trading logic (simplified - see full version for complete logic)
            ohlcv = ohlcv_by_symbol[sym]
            px = float(prices[sym])
            
            outputs: Dict[str, StrategyOutput] = {
                name: strat.evaluate(ohlcv) for name, strat in self.strategies.items()
            }
            current_signals_by_symbol[sym] = {name: int(out.signal) for name, out in outputs.items()}
            
            # Risk exits
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
                    if not isinstance(res, OrderRejection):
                        fills.append(res)
                        self.repo.log_order_filled(order)
                        self.repo.log_fill(res)

            # Choose decision mode
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

        # Update equity history and trading metrics
        broker_portfolio = self.broker.portfolio()
        current_equity = float(broker_portfolio.cash) + sum(
            float(p.market_value(prices.get(p.symbol, 0.0))) for p in broker_portfolio.positions.values()
        )
        self.equity_history.append(current_equity)

        # Calculate metrics
        sharpe, max_dd, win_rate, num_trades, current_pnl = self._calculate_metrics()

        # Store for next iteration
        self._prev_prices = prices
        self._prev_signals_by_symbol = current_signals_by_symbol

        print(" [OK]", flush=True)

        # Build update with portfolio metrics
        sector_exposure = self.portfolio_mgr.get_sector_exposure() if self.portfolio_mgr else {}
        
        return EnhancedPaperEngineUpdate(
            ts=ts,
            iteration=self.iteration,
            mode=self.strategy_mode,
            prices=prices,
            signals=signals,
            decisions=decisions,
            fills=fills,
            rejections=rejections,
            portfolio=broker_portfolio,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            win_rate=win_rate,
            num_trades=num_trades,
            current_pnl=current_pnl,
            # NEW metrics
            portfolio_value=self.portfolio_mgr.total_value if self.portfolio_mgr else current_equity,
            invested_value=self.portfolio_mgr.invested_value if self.portfolio_mgr else 0.0,
            cash=self.portfolio_mgr.cash if self.portfolio_mgr else broker_portfolio.cash,
            leverage=self.portfolio_mgr.leverage if self.portfolio_mgr else 0.0,
            utilization_pct=self.portfolio_mgr.utilization if self.portfolio_mgr else 0.0,
            num_open_positions=self.portfolio_mgr.num_positions if self.portfolio_mgr else len(broker_portfolio.positions),
            sector_exposure=sector_exposure,
            circuit_breaker_triggered=circuit_triggered,
            circuit_breaker_reason=circuit_reason,
            data_quality_issues=self._data_quality_issues,
            critical_alerts=self._critical_alerts,
        )

    def __iter__(self) -> Iterator[EnhancedPaperEngineUpdate]:
        """Iterate through trading steps"""
        if self.cfg.iterations > 0:
            for _ in range(self.cfg.iterations):
                yield self.step()
                if self.cfg.sleep_seconds > 0:
                    time.sleep(self.cfg.sleep_seconds)
        else:
            while True:
                yield self.step()
                if self.cfg.sleep_seconds > 0:
                    time.sleep(self.cfg.sleep_seconds)
