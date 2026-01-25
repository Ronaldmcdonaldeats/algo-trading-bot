"""
Position autocorrection engine.
Automatically detects and fixes position issues:
- Missing or expired stops
- Over-leveraged positions
- Stale positions (held too long)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import numpy as np


@dataclass
class PositionIssue:
    """Detected position issue"""
    symbol: str
    issue_type: str  # missing_stop, missing_tp, over_leveraged, stale, drawdown_exceeded
    severity: str  # low, medium, high, critical
    description: str
    recommended_action: str
    current_value: Optional[float] = None
    recommended_value: Optional[float] = None


@dataclass
class CorrectionAction:
    """Action to correct a position"""
    symbol: str
    action_type: str  # add_stop, tighten_stop, remove_position, reduce_size
    reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    shares_to_sell: Optional[int] = None


class PositionAutocorrector:
    """
    Automatically detect and correct position issues.
    Focuses on capital preservation and risk management.
    """
    
    def __init__(
        self,
        max_position_risk_pct: float = 2.0,  # Max risk per position
        max_drawdown_pct: float = 5.0,  # Exit if position down 5%
        max_hold_bars: int = 50,  # Max bars to hold a position
        min_confidence_for_trade: float = 0.3,  # Min signal confidence
    ):
        self.max_position_risk_pct = max_position_risk_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_hold_bars = max_hold_bars
        self.min_confidence_for_trade = min_confidence_for_trade
        
        self.issues_detected: Dict[str, List[PositionIssue]] = {}
        self.corrections_made: Dict[str, List[CorrectionAction]] = {}
    
    def scan_positions(
        self,
        positions: Dict,
        prices: Dict[str, float],
        equity: float,
        entry_bars: Dict[str, int],
        entry_prices: Dict[str, float],
        current_bar: int,
    ) -> List[PositionIssue]:
        """
        Scan all positions for issues
        
        Args:
            positions: Dict of symbol -> Position objects with qty, stop_loss, take_profit
            prices: Current prices by symbol
            equity: Current portfolio equity
            entry_bars: Bar number where each position was entered
            entry_prices: Entry price for each position
            current_bar: Current bar number
            
        Returns:
            List of detected issues
        """
        issues = []
        self.issues_detected.clear()
        
        for symbol, position in positions.items():
            if position.qty == 0:
                continue  # Skip flat positions
            
            current_price = prices.get(symbol, 0)
            if current_price <= 0:
                continue
            
            symbol_issues = []
            
            # Check 1: Missing stop loss
            if position.stop_loss is None or position.stop_loss <= 0:
                issue = PositionIssue(
                    symbol=symbol,
                    issue_type="missing_stop",
                    severity="high",
                    description=f"{symbol} position has no stop loss",
                    recommended_action=f"Add stop loss at {current_price * 0.97:.2f} (3% below entry)",
                    current_value=None,
                    recommended_value=current_price * 0.97,
                )
                symbol_issues.append(issue)
            
            # Check 2: Over-leveraged position
            position_risk = abs(position.qty) * current_price / equity * 100
            if position_risk > self.max_position_risk_pct * 3:  # 3x allowed risk
                issue = PositionIssue(
                    symbol=symbol,
                    issue_type="over_leveraged",
                    severity="critical",
                    description=f"{symbol} risk {position_risk:.1f}% of equity (max {self.max_position_risk_pct * 3:.1f}%)",
                    recommended_action=f"Reduce position size to {int(position.qty * self.max_position_risk_pct / (position_risk + 1e-6))} shares",
                    current_value=position_risk,
                    recommended_value=self.max_position_risk_pct,
                )
                symbol_issues.append(issue)
            
            # Check 3: Position held too long without profit
            if symbol in entry_bars:
                bars_held = current_bar - entry_bars[symbol]
                if bars_held > self.max_hold_bars:
                    entry_price = entry_prices.get(symbol, current_price)
                    profit_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                    
                    if profit_pct < 0.5:  # Less than 0.5% profit
                        issue = PositionIssue(
                            symbol=symbol,
                            issue_type="stale",
                            severity="medium",
                            description=f"{symbol} held {bars_held} bars with only {profit_pct:.2f}% profit",
                            recommended_action=f"Close position (capital could be used elsewhere)",
                            current_value=bars_held,
                            recommended_value=0,
                        )
                        symbol_issues.append(issue)
            
            # Check 4: Drawdown exceeded
            if symbol in entry_prices:
                entry_price = entry_prices[symbol]
                loss_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                
                if loss_pct < -self.max_drawdown_pct:
                    issue = PositionIssue(
                        symbol=symbol,
                        issue_type="drawdown_exceeded",
                        severity="high",
                        description=f"{symbol} down {loss_pct:.2f}% (max {self.max_drawdown_pct:.1f}%)",
                        recommended_action="Close position to preserve capital",
                        current_value=loss_pct,
                        recommended_value=0,
                    )
                    symbol_issues.append(issue)
            
            # Check 5: Missing take profit
            if position.take_profit is None or position.take_profit <= 0:
                # Suggest take profit at 2% above entry
                if symbol in entry_prices:
                    entry_price = entry_prices[symbol]
                    suggested_tp = entry_price * 1.02
                    issue = PositionIssue(
                        symbol=symbol,
                        issue_type="missing_tp",
                        severity="low",
                        description=f"{symbol} position has no take profit",
                        recommended_action=f"Add take profit at {suggested_tp:.2f} (2% above entry)",
                        current_value=None,
                        recommended_value=suggested_tp,
                    )
                    symbol_issues.append(issue)
            
            if symbol_issues:
                self.issues_detected[symbol] = symbol_issues
                issues.extend(symbol_issues)
        
        return issues
    
    def recommend_corrections(
        self,
        issues: List[PositionIssue],
        positions: Dict,
        prices: Dict[str, float],
        entry_prices: Dict[str, float],
    ) -> List[CorrectionAction]:
        """
        Recommend corrections for detected issues
        
        Args:
            issues: List of detected issues
            positions: Current positions
            prices: Current prices
            entry_prices: Entry prices
            
        Returns:
            List of recommended corrections
        """
        corrections = []
        self.corrections_made.clear()
        
        for issue in issues:
            symbol = issue.symbol
            position = positions.get(symbol)
            current_price = prices.get(symbol, 0)
            entry_price = entry_prices.get(symbol, current_price)
            
            if position is None or position.qty == 0:
                continue
            
            if issue.issue_type == "missing_stop":
                # Add stop loss at 3% below entry
                stop_loss = entry_price * 0.97 if entry_price > 0 else current_price * 0.97
                correction = CorrectionAction(
                    symbol=symbol,
                    action_type="add_stop",
                    reason="Missing stop loss protection",
                    stop_loss=stop_loss,
                )
                corrections.append(correction)
                
                if symbol not in self.corrections_made:
                    self.corrections_made[symbol] = []
                self.corrections_made[symbol].append(correction)
            
            elif issue.issue_type == "over_leveraged":
                # Reduce position size
                shares_to_sell = int(position.qty * 0.4)  # Sell 40% to reduce risk
                correction = CorrectionAction(
                    symbol=symbol,
                    action_type="reduce_size",
                    reason=f"Over-leveraged: {issue.current_value:.1f}% risk",
                    shares_to_sell=shares_to_sell,
                )
                corrections.append(correction)
                
                if symbol not in self.corrections_made:
                    self.corrections_made[symbol] = []
                self.corrections_made[symbol].append(correction)
            
            elif issue.issue_type == "stale":
                # Close stale position
                correction = CorrectionAction(
                    symbol=symbol,
                    action_type="remove_position",
                    reason=f"Stale position held {issue.current_value:.0f} bars",
                )
                corrections.append(correction)
                
                if symbol not in self.corrections_made:
                    self.corrections_made[symbol] = []
                self.corrections_made[symbol].append(correction)
            
            elif issue.issue_type == "drawdown_exceeded":
                # Close losing position
                correction = CorrectionAction(
                    symbol=symbol,
                    action_type="remove_position",
                    reason=f"Drawdown {issue.current_value:.2f}% exceeded max {self.max_drawdown_pct:.1f}%",
                )
                corrections.append(correction)
                
                if symbol not in self.corrections_made:
                    self.corrections_made[symbol] = []
                self.corrections_made[symbol].append(correction)
            
            elif issue.issue_type == "missing_tp":
                # Add take profit at 2% above entry
                take_profit = entry_price * 1.02 if entry_price > 0 else current_price * 1.02
                correction = CorrectionAction(
                    symbol=symbol,
                    action_type="add_stop",  # Reuse add_stop for TP too
                    reason="Missing take profit",
                    take_profit=take_profit,
                )
                corrections.append(correction)
                
                if symbol not in self.corrections_made:
                    self.corrections_made[symbol] = []
                self.corrections_made[symbol].append(correction)
        
        return corrections
    
    def get_critical_issues(self) -> List[PositionIssue]:
        """Get all critical/high severity issues"""
        critical = []
        for issues_list in self.issues_detected.values():
            critical.extend([i for i in issues_list if i.severity in ["critical", "high"]])
        return critical
    
    def print_summary(self):
        """Print autocorrection summary"""
        if not self.issues_detected:
            print("[AUTOCORRECT] No issues detected")
            return
        
        total_issues = sum(len(issues) for issues in self.issues_detected.values())
        critical_count = len(self.get_critical_issues())
        
        print(f"\n[AUTOCORRECT REPORT]")
        print(f"  Total issues: {total_issues} | Critical: {critical_count}")
        
        for symbol, issues in self.issues_detected.items():
            print(f"  {symbol}:")
            for issue in issues:
                print(f"    - [{issue.severity}] {issue.issue_type}: {issue.description}")
                print(f"      → {issue.recommended_action}")
