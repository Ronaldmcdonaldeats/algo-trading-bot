from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from trading_bot.core.models import Fill, Order, Portfolio
from trading_bot.db.models import (
    Base,
    AdaptiveDecisionEvent,
    FillEvent,
    LearningStateEvent,
    OrderEvent,
    PortfolioSnapshot,
    PositionSnapshot,
    RegimeHistoryEvent,
    StrategyDecisionEvent,
)
from trading_bot.strategy.base import StrategyDecision


@dataclass(frozen=True)
class SqliteRepository:
    db_path: Path = Path("data/trades.sqlite")

    def _engine(self):
        # OPTIMIZATION: Connection pooling for repeated writes
        return create_engine(
            f"sqlite:///{self.db_path}",
            poolclass=None,  # SQLite uses in-thread pooling
            connect_args={"timeout": 10.0, "check_same_thread": False},
        )

    def init_db(self) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)

    def log_order_filled(self, order: Order) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                OrderEvent(
                    id=order.id,
                    ts=order.ts,
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    type=order.type,
                    limit_price=order.limit_price,
                    tag=order.tag,
                    status="FILLED",
                    reject_reason="",
                )
            )
            session.commit()

    def log_order_rejected(self, order: Order, *, reason: str) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                OrderEvent(
                    id=order.id,
                    ts=order.ts,
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    type=order.type,
                    limit_price=order.limit_price,
                    tag=order.tag,
                    status="REJECTED",
                    reject_reason=reason,
                )
            )
            session.commit()

    def log_fill(self, fill: Fill) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                FillEvent(
                    order_id=fill.order_id,
                    ts=fill.ts,
                    symbol=fill.symbol,
                    side=fill.side,
                    qty=fill.qty,
                    price=fill.price,
                    fee=fill.fee,
                    slippage=fill.slippage,
                    note=fill.note,
                )
            )
            session.commit()

    def log_snapshot(self, *, ts: datetime, portfolio: Portfolio, prices: dict[str, float]) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            equity = portfolio.equity(prices)
            unrl = portfolio.unrealized_pnl(prices)
            session.add(
                PortfolioSnapshot(
                    ts=ts,
                    cash=float(portfolio.cash),
                    equity=float(equity),
                    unrealized_pnl=float(unrl),
                    fees_paid=float(portfolio.fees_paid),
                )
            )
            for sym, pos in portfolio.positions.items():
                if pos.qty == 0:
                    continue
                last = float(prices.get(sym, 0.0))
                session.add(
                    PositionSnapshot(
                        ts=ts,
                        symbol=sym,
                        qty=int(pos.qty),
                        avg_price=float(pos.avg_price),
                        last_price=last,
                        unrealized_pnl=float(pos.unrealized_pnl(last)),
                    )
                )
            session.commit()

    def recent_fills(self, *, limit: int = 10) -> list[FillEvent]:
        engine = self._engine()
        with Session(engine) as session:
            stmt = select(FillEvent).order_by(FillEvent.ts.desc()).limit(int(limit))
            return list(session.scalars(stmt).all())

    def latest_portfolio_snapshot(self) -> Optional[PortfolioSnapshot]:
        engine = self._engine()
        with Session(engine) as session:
            stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(1)
            return session.scalars(stmt).first()

    def latest_position_snapshots(self) -> list[PositionSnapshot]:
        engine = self._engine()
        with Session(engine) as session:
            latest_stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.ts.desc()).limit(1)
            latest = session.scalars(latest_stmt).first()
            if latest is None:
                return []
            stmt = select(PositionSnapshot).where(PositionSnapshot.ts == latest.ts)
            return list(session.scalars(stmt).all())

    def log_strategy_decision(
        self,
        *,
        ts: datetime,
        symbol: str,
        mode: str,
        decision: StrategyDecision,
    ) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                StrategyDecisionEvent(
                    ts=ts,
                    symbol=symbol,
                    mode=str(mode),
                    signal=int(decision.signal),
                    confidence=float(decision.confidence),
                    votes_json=json.dumps(decision.votes, sort_keys=True),
                    weights_json=json.dumps(decision.weights, sort_keys=True),
                    explanations_json=json.dumps(decision.explanations, sort_keys=True),
                )
            )
            session.commit()

    def log_learning_state(
        self,
        *,
        ts: datetime,
        weights: Dict[str, float],
        params: Dict[str, Dict[str, Any]],
        note: str = "",
    ) -> None:
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                LearningStateEvent(
                    ts=ts,
                    weights_json=json.dumps(weights, sort_keys=True),
                    params_json=json.dumps(params, sort_keys=True),
                    note=str(note),
                )
            )
            session.commit()

    def latest_learning_state(self) -> Optional[LearningStateEvent]:
        engine = self._engine()
        with Session(engine) as session:
            stmt = select(LearningStateEvent).order_by(LearningStateEvent.ts.desc()).limit(1)
            return session.scalars(stmt).first()
    def log_adaptive_decision(
        self,
        *,
        ts: datetime,
        regime: str,
        regime_confidence: float,
        adjusted_weights: Dict[str, float],
        param_recommendations: Dict[str, Dict[str, Any]],
        anomalies: list[str],
        explanation: Dict[str, Any],
    ) -> None:
        """Log adaptive learning decision for audit trail."""
        engine = self._engine()
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                AdaptiveDecisionEvent(
                    ts=ts,
                    regime=str(regime),
                    regime_confidence=float(regime_confidence),
                    adjusted_weights_json=json.dumps(adjusted_weights, sort_keys=True),
                    param_recommendations_json=json.dumps(param_recommendations, sort_keys=True),
                    anomalies_json=json.dumps(anomalies),
                    explanation_json=json.dumps(explanation, sort_keys=True, default=str),
                )
            )
            session.commit()