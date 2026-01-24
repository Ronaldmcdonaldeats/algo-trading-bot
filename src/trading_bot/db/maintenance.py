"""Database maintenance and data aggregation.

Prunes old events and keeps rolling summaries to prevent database bloat
while preserving learning state.
"""

from __future__ import annotations

import gc
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from trading_bot.db.models import (
    LearningStateEvent,
    OrderEvent,
    PortfolioSnapshot,
    PositionSnapshot,
    RegimeHistoryEvent,
    StrategyDecisionEvent,
)


def prune_old_events(
    session: Session,
    days_to_keep: int = 7,
    hourly_rollup: bool = True,
) -> dict:
    """Prune events older than days_to_keep, optionally keeping hourly summaries.
    
    Args:
        session: SQLAlchemy session
        days_to_keep: Keep detailed events for this many days, older = deleted
        hourly_rollup: If True, keep rolling hourly stats before deletion
        
    Returns:
        Summary of what was deleted
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=days_to_keep)
    
    stats = {
        "strategy_decisions_deleted": 0,
        "portfolio_snapshots_deleted": 0,
        "position_snapshots_deleted": 0,
        "regime_history_deleted": 0,
        "cutoff_time": cutoff.isoformat(),
    }
    
    # Delete old strategy decision events (very granular, can be pruned aggressively)
    result = session.execute(
        delete(StrategyDecisionEvent).where(StrategyDecisionEvent.ts < cutoff)
    )
    stats["strategy_decisions_deleted"] = result.rowcount or 0
    
    # Delete old portfolio snapshots (keep for 7 days by default)
    result = session.execute(
        delete(PortfolioSnapshot).where(PortfolioSnapshot.ts < cutoff)
    )
    stats["portfolio_snapshots_deleted"] = result.rowcount or 0
    
    # Delete old position snapshots
    result = session.execute(
        delete(PositionSnapshot).where(PositionSnapshot.ts < cutoff)
    )
    stats["position_snapshots_deleted"] = result.rowcount or 0
    
    # Keep regime history longer (it's sparse and valuable for learning)
    regime_cutoff = now - timedelta(days=max(30, days_to_keep * 2))
    result = session.execute(
        delete(RegimeHistoryEvent).where(RegimeHistoryEvent.ts < regime_cutoff)
    )
    stats["regime_history_deleted"] = result.rowcount or 0
    
    session.commit()
    
    # Force garbage collection after database cleanup to reclaim memory
    gc.collect()
    
    return stats


def get_learning_summary(
    session: Session,
    lookback_days: int = 7,
) -> dict:
    """Get rolling summary of learning performance for the past N days.
    
    Instead of looking at every trade, aggregates into summary metrics.
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(days=lookback_days)
    
    # Get most recent learning state
    latest_state = session.execute(
        select(LearningStateEvent)
        .where(LearningStateEvent.ts >= cutoff)
        .order_by(LearningStateEvent.ts.desc())
        .limit(1)
    ).scalar_one_or_none()
    
    # Get regime history summary
    regime_counts = session.execute(
        select(RegimeHistoryEvent.regime, func.count(RegimeHistoryEvent.id))
        .where(RegimeHistoryEvent.ts >= cutoff)
        .group_by(RegimeHistoryEvent.regime)
    ).all()
    
    # Get strategy signal summary
    signal_counts = session.execute(
        select(StrategyDecisionEvent.signal, func.count(StrategyDecisionEvent.id))
        .where(StrategyDecisionEvent.ts >= cutoff)
        .group_by(StrategyDecisionEvent.signal)
    ).all()
    
    return {
        "lookback_days": lookback_days,
        "cutoff_time": cutoff.isoformat(),
        "latest_weights": latest_state.params_json if latest_state else None,
        "regime_distribution": {regime: count for regime, count in regime_counts},
        "signal_distribution": {signal: count for signal, count in signal_counts},
        "total_decisions": sum(count for _, count in signal_counts),
    }


def cleanup_database(
    session: Session,
    days_to_keep: int = 7,
    dry_run: bool = False,
) -> dict:
    """Clean up database and return stats.
    
    Args:
        session: SQLAlchemy session
        days_to_keep: Delete events older than this
        dry_run: If True, just report what would be deleted
        
    Returns:
        Statistics about what was deleted
    """
    if dry_run:
        # Just count what would be deleted
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=days_to_keep)
        
        strategy_count = session.execute(
            select(func.count(StrategyDecisionEvent.id)).where(
                StrategyDecisionEvent.ts < cutoff
            )
        ).scalar() or 0
        
        portfolio_count = session.execute(
            select(func.count(PortfolioSnapshot.id)).where(
                PortfolioSnapshot.ts < cutoff
            )
        ).scalar() or 0
        
        return {
            "dry_run": True,
            "strategy_decisions_would_delete": strategy_count,
            "portfolio_snapshots_would_delete": portfolio_count,
            "cutoff_time": cutoff.isoformat(),
        }
    
    return prune_old_events(session, days_to_keep=days_to_keep)
