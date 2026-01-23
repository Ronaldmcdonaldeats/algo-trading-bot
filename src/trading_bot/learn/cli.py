"""Learning CLI commands for inspecting learning state during paper trading."""

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select, desc
from sqlalchemy.orm import Session

from trading_bot.db.models import (
    RegimeHistoryEvent,
    AdaptiveDecisionEvent,
    PerformanceMetricsEvent,
)


def _get_session(db_path: str) -> Session:
    """Create SQLAlchemy session from SQLite DB path."""
    db_url = f"sqlite:///{Path(db_path).absolute()}"
    engine = create_engine(db_url)
    return Session(engine)


def learn_inspect_cmd(db_path: str = "trades.sqlite", limit: int = 10) -> int:
    """Show current regime, weights, and recent decisions."""
    print("=" * 80)
    print("LEARNING STATE INSPECTOR")
    print("=" * 80)

    try:
        session = _get_session(db_path)

        # Latest regime history
        print("\n[MARKET REGIME]")
        print("-" * 80)
        regime_query = select(RegimeHistoryEvent).order_by(desc(RegimeHistoryEvent.ts)).limit(1)
        latest_regime = session.scalar(regime_query)

        if latest_regime:
            metrics = json.loads(latest_regime.metrics_json) if latest_regime.metrics_json else {}
            print(f"  Timestamp:    {latest_regime.ts}")
            print(f"  Regime:       {latest_regime.regime}")
            print(f"  Confidence:   {latest_regime.confidence:.1%}")
            print(f"  Volatility:   {latest_regime.volatility:.3f}")
            print(f"  Trend Str:    {latest_regime.trend_strength:.3f}")
            if metrics:
                print(f"  Metrics:      {json.dumps(metrics, indent=15)}")
        else:
            print("  (No regime history yet)")

        # Latest adaptive decision
        print("\n[ADAPTIVE DECISION]")
        print("-" * 80)
        decision_query = (
            select(AdaptiveDecisionEvent).order_by(desc(AdaptiveDecisionEvent.ts)).limit(1)
        )
        latest_decision = session.scalar(decision_query)

        if latest_decision:
            weights = (
                json.loads(latest_decision.adjusted_weights_json)
                if latest_decision.adjusted_weights_json
                else {}
            )
            anomalies = (
                json.loads(latest_decision.anomalies_json)
                if latest_decision.anomalies_json
                else []
            )
            print(f"  Timestamp:    {latest_decision.ts}")
            print(f"  Regime:       {latest_decision.regime}")
            print(f"  Regime Conf:  {latest_decision.regime_confidence:.1%}")
            print(f"  Adjusted Weights:")
            for strategy, weight in weights.items():
                print(f"    {strategy:20s}: {weight:.4f}")
            if anomalies:
                print(f"  Anomalies: {len(anomalies)}")
                for anom in anomalies[:3]:
                    print(f"    - {anom}")
            if latest_decision.explanation_json:
                explanation = json.loads(latest_decision.explanation_json)
                print(f"\n  Explanation:")
                for key, val in explanation.items():
                    if key == "adjusted_weights" and isinstance(val, dict):
                        print(f"    adjusted_weights:")
                        for strat, w in val.items():
                            print(f"      {strat:20s}: {w:.4f}")
                    elif key == "learned_weights" and isinstance(val, dict):
                        print(f"    learned_weights:")
                        for strat, w in val.items():
                            print(f"      {strat:20s}: {w:.4f}")
                    elif key == "regime_metrics" and isinstance(val, dict):
                        print(f"    regime_metrics:")
                        for metric, v in val.items():
                            if isinstance(v, float):
                                print(f"      {metric:20s}: {v:.4f}")
                            else:
                                print(f"      {metric:20s}: {v}")
                    elif key == "regime_symbols" and isinstance(val, dict):
                        print(f"    regime_symbols:")
                        for sym, regime in val.items():
                            print(f"      {sym:20s}: {regime}")
                    elif key == "performance" and isinstance(val, dict):
                        print(f"    performance:")
                        for metric, v in val.items():
                            if v is None:
                                print(f"      {metric:20s}: N/A")
                            elif isinstance(v, float):
                                if metric in ["total_return", "max_drawdown", "win_rate"]:
                                    print(f"      {metric:20s}: {v:.1%}")
                                elif metric == "profit_factor":
                                    print(f"      {metric:20s}: {v:.2f}")
                                else:
                                    print(f"      {metric:20s}: {v:.4f}")
                            else:
                                print(f"      {metric:20s}: {v}")
                    elif key == "strategy_analysis" and isinstance(val, dict):
                        if val:
                            print(f"    strategy_analysis:")
                            for strat, analysis in val.items():
                                print(f"      {strat}: {analysis}")
                    elif key == "regime":
                        print(f"    regime: {val}")
                    else:
                        print(f"    {key:20s}: {val}")
        else:
            print("  (No adaptive decisions yet)")

        # Recent metrics
        print("\n[PERFORMANCE METRICS]")
        print("-" * 80)
        metrics_query = (
            select(PerformanceMetricsEvent).order_by(desc(PerformanceMetricsEvent.ts)).limit(3)
        )
        recent_metrics = session.scalars(metrics_query).all()

        if recent_metrics:
            for i, m in enumerate(recent_metrics, 1):
                print(
                    f"  [{i}] {m.ts} | Sharpe: {m.sharpe_ratio:6.2f} | DD: {m.max_drawdown:6.1%} | WR: {m.win_rate:5.1%}"
                )
        else:
            print("  (No performance metrics yet)")

        session.close()
        print("\n" + "=" * 80)
        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1


def learn_history_cmd(db_path: str = "trades.sqlite", limit: int = 20) -> int:
    """Show regime history."""
    print("=" * 80)
    print("REGIME HISTORY")
    print("=" * 80)

    try:
        session = _get_session(db_path)

        history_query = (
            select(RegimeHistoryEvent).order_by(desc(RegimeHistoryEvent.ts)).limit(limit)
        )
        history = session.scalars(history_query).all()

        if not history:
            print("\n(No regime history yet)")
            session.close()
            return 0

        print(f"\n{'Timestamp':<20} {'Regime':<15} {'Confidence':<12} {'Volatility':<12} {'Trend':<10}")
        print("-" * 80)

        for event in reversed(history):  # Show oldest first
            print(
                f"{str(event.ts):<20} {event.regime:<15} {event.confidence:>10.1%} {event.volatility:>10.3f} {event.trend_strength:>8.3f}"
            )

        session.close()
        print("\n" + "=" * 80)
        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1


def learn_decisions_cmd(db_path: str = "trades.sqlite", limit: int = 10) -> int:
    """Show recent adaptive decisions."""
    print("=" * 80)
    print("ADAPTIVE DECISIONS")
    print("=" * 80)

    try:
        session = _get_session(db_path)

        decisions_query = (
            select(AdaptiveDecisionEvent).order_by(desc(AdaptiveDecisionEvent.ts)).limit(limit)
        )
        decisions = session.scalars(decisions_query).all()

        if not decisions:
            print("\n(No adaptive decisions yet)")
            session.close()
            return 0

        for i, decision in enumerate(reversed(decisions), 1):  # Show oldest first
            weights = (
                json.loads(decision.adjusted_weights_json)
                if decision.adjusted_weights_json
                else {}
            )
            params = (
                json.loads(decision.param_recommendations_json)
                if decision.param_recommendations_json
                else {}
            )

            print(f"\n[{i}] {decision.ts}")
            print(f"    Regime: {decision.regime} (confidence: {decision.regime_confidence:.1%})")
            print("    Weights:")
            for strategy, weight in weights.items():
                print(f"      {strategy:20s}: {weight:.4f}")

            if params:
                print("    Parameter Recommendations:")
                for strategy, changes in params.items():
                    if changes:
                        print(f"      {strategy}:")
                        for param, change in changes.items():
                            print(f"        {param:20s}: {change}")

        session.close()
        print("\n" + "=" * 80)
        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1


def learn_metrics_cmd(db_path: str = "trades.sqlite", limit: int = 5) -> int:
    """Show performance metrics over time."""
    print("=" * 80)
    print("PERFORMANCE METRICS")
    print("=" * 80)

    try:
        session = _get_session(db_path)

        metrics_query = (
            select(PerformanceMetricsEvent).order_by(desc(PerformanceMetricsEvent.ts)).limit(limit)
        )
        metrics_list = session.scalars(metrics_query).all()

        if not metrics_list:
            print("\n(No performance metrics yet)")
            session.close()
            return 0

        print(
            f"\n{'Timestamp':<20} {'Return':<10} {'Sharpe':<10} {'Drawdown':<12} {'Win Rate':<10} {'PF':<8} {'Trades':<8}"
        )
        print("-" * 90)

        for m in reversed(metrics_list):  # Show oldest first
            pf = m.profit_factor if m.profit_factor else 0.0
            print(
                f"{str(m.ts):<20} {m.total_return:>8.1%} {m.sharpe_ratio:>8.2f} {m.max_drawdown:>10.1%} {m.win_rate:>8.1%} {pf:>6.2f} {m.trade_count:>6.0f}"
            )

        # Summary stats
        if metrics_list:
            latest = metrics_list[0]
            print("\n" + "-" * 90)
            print(f"Latest (Most Recent):")
            print(f"  Total Return:      {latest.total_return:.1%}")
            print(f"  Sharpe Ratio:      {latest.sharpe_ratio:.2f}")
            print(f"  Max Drawdown:      {latest.max_drawdown:.1%}")
            print(f"  Win Rate:          {latest.win_rate:.1%}")
            print(f"  Profit Factor:     {latest.profit_factor:.2f}" if latest.profit_factor else "  Profit Factor:     N/A")
            print(f"  Total Trades:      {int(latest.trade_count)}")
            print(f"  Winning Trades:    {int(latest.winning_trades)}")
            print(f"  Losing Trades:     {int(latest.losing_trades)}")

        session.close()
        print("\n" + "=" * 80)
        return 0

    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1
