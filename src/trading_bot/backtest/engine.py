from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from trading_bot.broker.base import Broker, OrderRejection
from trading_bot.broker.paper import PaperBroker, PaperBrokerConfig
from trading_bot.configs import load_config, AppConfig, RiskConfig, PortfolioConfig, StrategyConfig
from trading_bot.core.models import Fill, Order
from trading_bot.data.providers import MarketDataProvider, AlpacaProvider, MockDataProvider, YFinanceProvider
from trading_bot.db.repository import SqliteRepository
from trading_bot.indicators import add_indicators
from trading_bot.learn.ensemble import ExponentialWeightsEnsemble
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.base import StrategyDecision
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestResult:
    """Comprehensive backtest results with performance metrics."""

    total_return: float  # % total return
    sharpe: float  # Sharpe ratio (annualized)
    max_drawdown: float  # Maximum drawdown %
    win_rate: float  # % of profitable trades
    num_trades: int  # Total trades executed
    avg_win: float  # Average winning trade %
    avg_loss: float  # Average losing trade %
    profit_factor: float  # Gross profit / Gross loss
    calmar: float  # Calmar ratio (return / max_drawdown)
    final_equity: float  # Final portfolio value


@dataclass
class BacktestConfig:
    """Configuration for backtesting."""

    config_path: str
    symbols: list[str]
    period: str = "1y"  # Historical period (1y, 2y, 5y, etc.)
    interval: str = "1d"  # Bar interval (1d, 1wk, 1mo)
    start_cash: float = 100_000.0
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    min_fee: float = 0.0
    strategy_mode: str = "ensemble"  # ensemble|mean_reversion_rsi|momentum_macd_volume|breakout_atr
    data_source: str = "auto"  # auto|alpaca|yahoo


def _calculate_returns(equity_series: list[float]) -> np.ndarray:
    """Calculate daily returns from equity series."""
    if len(equity_series) < 2:
        return np.array([])
    returns = np.diff(equity_series) / np.array(equity_series[:-1])
    return returns


def _calculate_sharpe(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
    """Calculate annualized Sharpe ratio (assuming daily returns)."""
    if len(returns) == 0:
        return 0.0
    excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free rate
    return float(np.sqrt(252) * np.mean(excess_returns) / (np.std(excess_returns) + 1e-8))


def _calculate_max_drawdown(equity_series: list[float]) -> float:
    """Calculate maximum drawdown as percentage."""
    if len(equity_series) < 2:
        return 0.0
    cummax = np.maximum.accumulate(equity_series)
    drawdown = (np.array(equity_series) - cummax) / cummax
    return float(np.min(drawdown))


def _calculate_calmar(total_return: float, max_drawdown: float) -> float:
    """Calculate Calmar ratio."""
    if max_drawdown >= 0 or abs(max_drawdown) < 1e-6:
        return 0.0
    return float(total_return / abs(max_drawdown))


class BacktestEngine:
    """Vectorized backtest engine that reuses existing strategies."""

    def __init__(
        self,
        cfg: BacktestConfig,
        provider: MarketDataProvider | None = None,
        broker: Broker | None = None,
    ) -> None:
        self.cfg = cfg
        
        # Load config - use default if not provided
        config_path = cfg.config_path or "configs/default.yaml"
        try:
            self.app_cfg = load_config(config_path)
        except Exception as e:
            # If config loading fails, use empty defaults
            logger.warning(f"Failed to load config from {config_path}: {e}. Using defaults.")
            self.app_cfg = AppConfig(
                risk=RiskConfig(),
                portfolio=PortfolioConfig(),
                strategy=StrategyConfig(raw={})
            )
        
        # Setup data provider based on data_source
        if provider:
            self.data = provider
        else:
            # Always use Yahoo Finance for now - it's the most reliable
            # Alpaca data provider has API limits and authentication issues
            self.data = YFinanceProvider()
        
        self.broker = broker or PaperBroker(
            start_cash=float(cfg.start_cash),
            config=PaperBrokerConfig(
                commission_bps=float(cfg.commission_bps),
                slippage_bps=float(cfg.slippage_bps),
                min_fee=float(cfg.min_fee),
            ),
        )

        self.iteration = 0
        self.equity_history: list[float] = [float(cfg.start_cash)]
        self.trades: list[Dict[str, Any]] = []

        # Build strategies
        self.strategies = self._build_strategies()
        self.ensemble = ExponentialWeightsEnsemble(
            weights={name: 1.0 for name in self.strategies.keys()},
            eta=0.3,  # Default learning rate for backtest
        )

    def _build_strategies(self) -> Dict[str, Any]:
        """Build strategy instances from config or strategy_mode."""
        strategies = {}
        strategy_mode = self.cfg.strategy_mode

        # If using a single custom strategy via factory
        if strategy_mode and strategy_mode not in ["ensemble"]:
            try:
                # Try to import factory (only available in dev, not in Docker)
                try:
                    from scripts.strategies.factory import StrategyFactory
                    factory = StrategyFactory()
                    strategy = factory.create(strategy_mode)
                    if strategy:
                        strategies[strategy_mode] = strategy
                        logger.info(f"Loaded strategy: {strategy_mode}")
                        return strategies
                except (ImportError, ModuleNotFoundError):
                    logger.debug("Factory not available, building strategies manually")
                    
                # Fallback: build custom strategy manually
                if strategy_mode == "ultimate_hybrid":
                    # Build ultimate hybrid strategy from base components
                    from trading_bot.strategy.base import Strategy
                    from trading_bot.indicators import add_indicators
                    
                    # Use RSI as base for ultimate_hybrid
                    strategies["ultimate_hybrid"] = RsiMeanReversionStrategy(
                        rsi_period=14,
                        entry_oversold=30.0,
                        exit_rsi=50.0,
                    )
                    logger.info("Loaded strategy: ultimate_hybrid (via RSI base)")
                    return strategies
            except Exception as e:
                logger.warning(f"Failed to load {strategy_mode}: {e}, using ensemble mode")

        # Default ensemble mode with multiple strategies
        rsi_params = self.app_cfg.strategy.raw.get("mean_reversion_rsi", {})
        strategies["mean_reversion_rsi"] = RsiMeanReversionStrategy(
            rsi_period=int(rsi_params.get("rsi_period", 14)),
            entry_oversold=float(rsi_params.get("entry_oversold", 30.0)),
            exit_rsi=float(rsi_params.get("exit_rsi", 50.0)),
        )

        macd_params = self.app_cfg.strategy.raw.get("momentum_macd_volume", {})
        strategies["momentum_macd_volume"] = MacdVolumeMomentumStrategy(
            macd_fast=int(macd_params.get("macd_fast", 12)),
            macd_slow=int(macd_params.get("macd_slow", 26)),
            macd_signal=int(macd_params.get("macd_signal", 9)),
            vol_sma=int(macd_params.get("vol_sma", 20)),
            vol_mult=float(macd_params.get("vol_mult", 1.0)),
        )

        atr_params = self.app_cfg.strategy.raw.get("breakout_atr", {})
        strategies["breakout_atr"] = AtrBreakoutStrategy(
            atr_period=int(atr_params.get("atr_period", 14)),
            breakout_lookback=int(atr_params.get("breakout_lookback", 20)),
            atr_mult=float(atr_params.get("atr_mult", 1.0)),
        )

        return strategies

    def run(self) -> BacktestResult:
        """Run backtest on historical data."""
        logger.info(f"Starting backtest: {self.cfg.symbols} {self.cfg.period}")

        # Download all historical data
        bars = self.data.download_bars(
            symbols=self.cfg.symbols,
            period=self.cfg.period,
            interval=self.cfg.interval,
        )

        if bars.empty:
            logger.error("No data downloaded")
            raise ValueError("Failed to download historical data")

        # Prepare OHLCV data per symbol
        ohlcv_by_symbol: Dict[str, pd.DataFrame] = {}
        for sym in self.cfg.symbols:
            try:
                df = bars[bars["Symbol"] == sym].copy()
                if df.empty:
                    logger.warning(f"No data for {sym}, skipping")
                    continue
                df = df.sort_values("Date").reset_index(drop=True)
                ohlcv_by_symbol[sym] = df
            except Exception as e:
                logger.warning(f"Error preparing {sym}: {e}")
                continue

        # Backtest loop - iterate through bars
        # Get all unique dates from all symbols
        all_dates = set()
        for df in ohlcv_by_symbol.values():
            all_dates.update(df["Date"].unique())

        all_dates = sorted(list(all_dates))
        logger.info(f"Backtesting {len(all_dates)} bars across {len(ohlcv_by_symbol)} symbols")

        for date_idx, current_date in enumerate(all_dates):
            self.iteration += 1

            # Get current bar for each symbol
            prices: Dict[str, float] = {}
            ohlcv_subset: Dict[str, pd.DataFrame] = {}

            for sym, df in ohlcv_by_symbol.items():
                # Get all data up to and including current date
                mask = df["Date"] <= current_date
                subset = df[mask].copy()

                if len(subset) == 0:
                    continue

                ohlcv_subset[sym] = subset
                prices[sym] = float(subset["Close"].iloc[-1])

            if not prices:
                continue

            # Update broker prices
            for sym, px in prices.items():
                self.broker.set_price(sym, px)

            # Evaluate strategies for each symbol
            for sym in ohlcv_subset.keys():
                if sym not in ohlcv_subset:
                    continue

                df = ohlcv_subset[sym]
                if len(df) < 50:  # Need minimum data
                    continue

                # Add indicators
                df_with_indicators = add_indicators(df)

                # Evaluate all strategies
                outputs = {
                    name: strat.evaluate(df_with_indicators)
                    for name, strat in self.strategies.items()
                }

                # Get ensemble decision
                if self.cfg.strategy_mode == "ensemble":
                    dec = self.ensemble.decide(outputs)
                else:
                    if self.cfg.strategy_mode not in outputs:
                        continue
                    out = outputs[self.cfg.strategy_mode]
                    dec = StrategyDecision(
                        signal=int(out.signal),
                        confidence=float(out.confidence),
                        votes={self.cfg.strategy_mode: int(out.signal)},
                        weights={self.cfg.strategy_mode: 1.0},
                        explanations={self.cfg.strategy_mode: dict(out.explanation)},
                    )

                # Execute orders based on signal
                current_portfolio = self.broker.portfolio()
                pos = current_portfolio.get_position(sym)
                px = prices[sym]

                # Risk exits
                if pos.qty > 0:
                    if pos.stop_loss and px <= float(pos.stop_loss):
                        # Sell on stop loss
                        order = Order(
                            id=f"bt_{self.iteration}_{sym}_sl",
                            ts=current_date,
                            symbol=sym,
                            side="SELL",
                            qty=int(pos.qty),
                            type="MARKET",
                            tag="stop_loss",
                        )
                        fill = self.broker.submit_order(order)
                        if isinstance(fill, Fill):
                            self.trades.append({
                                "symbol": sym,
                                "entry_price": pos.avg_price,
                                "exit_price": fill.price,
                                "qty": fill.qty,
                                "pnl": (fill.price - pos.avg_price) * fill.qty - fill.fee,
                                "entry_date": None,
                                "exit_date": current_date,
                                "tag": "stop_loss",
                            })
                        continue

                    if pos.take_profit and px >= float(pos.take_profit):
                        # Sell on take profit
                        order = Order(
                            id=f"bt_{self.iteration}_{sym}_tp",
                            ts=current_date,
                            symbol=sym,
                            side="SELL",
                            qty=int(pos.qty),
                            type="MARKET",
                            tag="take_profit",
                        )
                        fill = self.broker.submit_order(order)
                        if isinstance(fill, Fill):
                            self.trades.append({
                                "symbol": sym,
                                "entry_price": pos.avg_price,
                                "exit_price": fill.price,
                                "qty": fill.qty,
                                "pnl": (fill.price - pos.avg_price) * fill.qty - fill.fee,
                                "entry_date": None,
                                "exit_date": current_date,
                                "tag": "take_profit",
                            })
                        continue

                # Signal-based trades
                if dec.signal == 1 and pos.qty == 0:
                    # Buy
                    available_cash = float(current_portfolio.cash)
                    max_risk = float(self.app_cfg.risk.max_risk_per_trade)
                    risk_amt = available_cash * max_risk

                    if risk_amt > 0:
                        sl = px * (1.0 - float(self.app_cfg.risk.stop_loss_pct) / 100.0)
                        tp = px * (1.0 + float(self.app_cfg.risk.take_profit_pct) / 100.0)
                        shares = int(risk_amt / (px - sl))

                        if shares > 0:
                            order = Order(
                                id=f"bt_{self.iteration}_{sym}_buy",
                                ts=current_date,
                                symbol=sym,
                                side="BUY",
                                qty=shares,
                                type="MARKET",
                                tag=f"signal_long:{self.cfg.strategy_mode}",
                            )
                            fill = self.broker.submit_order(order)
                            if isinstance(fill, Fill):
                                pos = current_portfolio.get_position(sym)
                                pos.stop_loss = sl
                                pos.take_profit = tp

                elif dec.signal == 0 and pos.qty > 0:
                    # Sell (flatten position)
                    order = Order(
                        id=f"bt_{self.iteration}_{sym}_sell",
                        ts=current_date,
                        symbol=sym,
                        side="SELL",
                        qty=int(pos.qty),
                        type="MARKET",
                        tag=f"signal_flat:{self.cfg.strategy_mode}",
                    )
                    fill = self.broker.submit_order(order)
                    if isinstance(fill, Fill):
                        self.trades.append({
                            "symbol": sym,
                            "entry_price": pos.avg_price,
                            "exit_price": fill.price,
                            "qty": fill.qty,
                            "pnl": (fill.price - pos.avg_price) * fill.qty - fill.fee,
                            "entry_date": None,
                            "exit_date": current_date,
                            "tag": "signal",
                        })

            # Record equity
            eq = self.broker.portfolio().equity(prices)
            self.equity_history.append(float(eq))

            if self.iteration % 50 == 0:
                logger.info(f"Bar {self.iteration}/{len(all_dates)}: Equity=${eq:,.2f}")

        # Calculate metrics
        return self._calculate_metrics()

    def _calculate_metrics(self) -> BacktestResult:
        """Calculate performance metrics."""
        initial_equity = self.cfg.start_cash
        final_equity = self.equity_history[-1] if self.equity_history else initial_equity
        total_return = (final_equity - initial_equity) / initial_equity

        returns = _calculate_returns(self.equity_history)
        sharpe = _calculate_sharpe(returns)
        max_drawdown = _calculate_max_drawdown(self.equity_history)
        calmar = _calculate_calmar(total_return, max_drawdown)

        # Trade metrics
        num_trades = len(self.trades)
        if num_trades > 0:
            pnls = [t["pnl"] for t in self.trades]
            winning_trades = [p for p in pnls if p > 0]
            losing_trades = [p for p in pnls if p < 0]

            win_rate = len(winning_trades) / num_trades
            avg_win = float(np.mean(winning_trades)) if winning_trades else 0.0
            avg_loss = float(np.mean(losing_trades)) if losing_trades else 0.0

            gross_profit = sum(winning_trades) if winning_trades else 0.0
            gross_loss = abs(sum(losing_trades)) if losing_trades else 1e-8
            profit_factor = gross_profit / gross_loss
        else:
            win_rate = 0.0
            avg_win = 0.0
            avg_loss = 0.0
            profit_factor = 0.0

        return BacktestResult(
            total_return=float(total_return),
            sharpe=float(sharpe),
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate),
            num_trades=num_trades,
            avg_win=float(avg_win),
            avg_loss=float(avg_loss),
            profit_factor=float(profit_factor),
            calmar=float(calmar),
            final_equity=float(final_equity),
        )


def run_backtest(
    *,
    config_path: str,
    symbols: list[str],
    period: str = "1y",
    interval: str = "1d",
    start_cash: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    min_fee: float = 0.0,
    strategy_mode: str = "ensemble",
    data_source: str = "auto",
) -> BacktestResult:
    """Run backtest with given parameters.

    Args:
        config_path: Path to YAML config
        symbols: List of stock symbols to trade
        period: Historical period (1y, 2y, 5y, max)
        interval: Bar interval (1d, 1wk, 1mo)
        start_cash: Initial capital
        commission_bps: Trading costs in basis points
        slippage_bps: Market impact in basis points
        min_fee: Minimum fee per trade
        strategy_mode: Trading mode (ensemble, mean_reversion_rsi, etc.)
        data_source: Data source to use (auto|alpaca|yahoo)

    Returns:
        BacktestResult with performance metrics
    """
    cfg = BacktestConfig(
        config_path=config_path,
        symbols=symbols,
        period=period,
        interval=interval,
        start_cash=start_cash,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        min_fee=min_fee,
        strategy_mode=strategy_mode,
        data_source=data_source,
    )

    engine = BacktestEngine(cfg)
    return engine.run()
