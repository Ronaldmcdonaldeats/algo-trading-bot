"""
Compliance & Audit Module
Immutable trade audit trail, position limits, market hours enforcement, regulatory logging.
Ensures regulatory compliance and provides comprehensive audit records.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, time, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ComplianceViolationType(Enum):
    """Types of compliance violations"""
    POSITION_LIMIT_EXCEEDED = "position_limit_exceeded"
    SECTOR_CONCENTRATION = "sector_concentration"
    GROSS_LEVERAGE_EXCEEDED = "gross_leverage_exceeded"
    MARKET_HOURS_VIOLATION = "market_hours_violation"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    WASH_SALE = "wash_sale"
    INSIDER_TRADING_FLAG = "insider_trading_flag"
    UNUSUAL_ACTIVITY = "unusual_activity"


@dataclass
class AuditRecord:
    """Immutable audit record"""
    record_id: str
    timestamp: datetime
    event_type: str  # "trade", "order", "position_change", "parameter_change"
    actor: str  # Who triggered (bot, user, system)
    symbol: str
    quantity: int
    price: float
    side: str  # "buy" or "sell"
    reason: str
    metadata: Dict = field(default_factory=dict)
    hash_value: str = ""  # SHA256 of this record
    previous_hash: str = ""  # For chain integrity

    def calculate_hash(self) -> str:
        """Calculate SHA256 hash of record"""
        record_str = json.dumps(asdict(self), default=str, sort_keys=True)
        return hashlib.sha256(record_str.encode()).hexdigest()

    def validate_integrity(self) -> bool:
        """Validate record hasn't been tampered with"""
        calculated_hash = self.calculate_hash()
        return calculated_hash == self.hash_value


@dataclass
class ComplianceViolation:
    """Compliance violation record"""
    violation_id: str
    violation_type: ComplianceViolationType
    timestamp: datetime
    symbol: str
    description: str
    severity: str  # "warning", "critical"
    action_taken: str  # How violation was handled
    metadata: Dict = field(default_factory=dict)


@dataclass
class RegulatoryReport:
    """Regulatory report (SEC, FINRA format)"""
    report_id: str
    report_date: datetime
    report_type: str  # "13F", "Form 4", "Trade Report"
    trades: List[Dict]
    positions: List[Dict]
    violations: List[ComplianceViolation]
    summary: Dict


class AuditTrail:
    """Maintains immutable audit trail using blockchain-like chain"""

    def __init__(self):
        self.records: List[AuditRecord] = []
        self.chain_head_hash = ""

    def add_record(
        self,
        event_type: str,
        actor: str,
        symbol: str,
        quantity: int,
        price: float,
        side: str,
        reason: str,
        metadata: Dict = None,
    ) -> str:
        """Add record to audit trail"""

        record_id = f"AUD_{int(datetime.now().timestamp() * 1000)}"
        record = AuditRecord(
            record_id=record_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            actor=actor,
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=side,
            reason=reason,
            metadata=metadata or {},
            previous_hash=self.chain_head_hash,
        )

        # Calculate hash
        record.hash_value = record.calculate_hash()

        # Update chain head
        self.chain_head_hash = record.hash_value

        self.records.append(record)
        logger.info(f"Audit record added: {record_id}")

        return record_id

    def get_audit_trail(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditRecord]:
        """Retrieve audit trail with optional filtering"""

        filtered = self.records

        if symbol:
            filtered = [r for r in filtered if r.symbol == symbol]

        if start_date:
            filtered = [r for r in filtered if r.timestamp >= start_date]

        if end_date:
            filtered = [r for r in filtered if r.timestamp <= end_date]

        return filtered

    def verify_chain_integrity(self) -> Tuple[bool, List[str]]:
        """Verify entire audit chain integrity"""
        errors = []
        previous_hash = ""

        for record in self.records:
            # Check record hash validity
            if not record.validate_integrity():
                errors.append(f"Record {record.record_id} has invalid hash")

            # Check chain continuity
            if record.previous_hash != previous_hash:
                errors.append(f"Record {record.record_id} has invalid previous hash")

            previous_hash = record.hash_value

        return len(errors) == 0, errors


class ComplianceMonitor:
    """Monitors trading for compliance violations"""

    def __init__(self):
        self.violations: List[ComplianceViolation] = []
        self.rules = self._initialize_rules()

    def _initialize_rules(self) -> Dict:
        """Initialize compliance rules"""
        return {
            "max_position_size_pct": 0.05,  # Max 5% per symbol
            "max_sector_concentration": 0.25,  # Max 25% per sector
            "max_gross_leverage": 3.0,
            "max_daily_loss_pct": 0.05,  # 5% daily loss limit
            "trading_hours_only": True,  # Only US market hours
            "wash_sale_detection": True,
            "position_limit_multiplier": 100,  # Max position = 100M shares
        }

    def check_position_limits(
        self,
        symbol: str,
        quantity: int,
        price: float,
        portfolio_value: float,
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        """Check position size limits"""

        position_value = quantity * price
        position_pct = position_value / portfolio_value if portfolio_value > 0 else 0

        max_position_pct = self.rules["max_position_size_pct"]

        if position_pct > max_position_pct:
            violation = ComplianceViolation(
                violation_id=f"POS_{int(datetime.now().timestamp())}",
                violation_type=ComplianceViolationType.POSITION_LIMIT_EXCEEDED,
                timestamp=datetime.now(),
                symbol=symbol,
                description=f"Position {position_pct*100:.2f}% exceeds {max_position_pct*100}% limit",
                severity="critical",
                action_taken="Order rejected",
                metadata={
                    "position_pct": position_pct,
                    "max_allowed": max_position_pct,
                    "quantity": quantity,
                    "price": price,
                },
            )
            self.violations.append(violation)
            return False, violation

        return True, None

    def check_sector_concentration(
        self,
        positions: Dict[str, int],
        prices: Dict[str, float],
        sector_map: Dict[str, str],
        portfolio_value: float,
    ) -> Tuple[bool, List[ComplianceViolation]]:
        """Check sector concentration limits"""

        violations = []
        sector_values = {}

        for symbol, qty in positions.items():
            sector = sector_map.get(symbol, "Unknown")
            price = prices.get(symbol, 0)
            sector_values[sector] = sector_values.get(sector, 0) + (qty * price)

        max_sector = self.rules["max_sector_concentration"]

        for sector, value in sector_values.items():
            sector_pct = value / portfolio_value if portfolio_value > 0 else 0

            if sector_pct > max_sector:
                violation = ComplianceViolation(
                    violation_id=f"SEC_{int(datetime.now().timestamp())}",
                    violation_type=ComplianceViolationType.SECTOR_CONCENTRATION,
                    timestamp=datetime.now(),
                    symbol=sector,
                    description=f"Sector {sector} concentration {sector_pct*100:.2f}% exceeds {max_sector*100}% limit",
                    severity="critical",
                    action_taken="Position rebalancing triggered",
                    metadata={"sector": sector, "concentration": sector_pct},
                )
                violations.append(violation)
                self.violations.append(violation)

        return len(violations) == 0, violations

    def check_market_hours(self, symbol: str, timestamp: datetime = None) -> Tuple[bool, Optional[ComplianceViolation]]:
        """Check if trading outside market hours"""

        if not self.rules["trading_hours_only"]:
            return True, None

        if timestamp is None:
            timestamp = datetime.now()

        # US market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
        market_open = time(9, 30)
        market_close = time(16, 0)

        # Check weekday (0=Monday, 4=Friday)
        if timestamp.weekday() > 4:  # Weekend
            violation = ComplianceViolation(
                violation_id=f"MKT_{int(datetime.now().timestamp())}",
                violation_type=ComplianceViolationType.MARKET_HOURS_VIOLATION,
                timestamp=timestamp,
                symbol=symbol,
                description=f"Trade outside market hours (Weekend)",
                severity="warning",
                action_taken="Order rejected",
            )
            self.violations.append(violation)
            return False, violation

        # Check time
        trade_time = timestamp.time()
        if trade_time < market_open or trade_time > market_close:
            violation = ComplianceViolation(
                violation_id=f"MKT_{int(datetime.now().timestamp())}",
                violation_type=ComplianceViolationType.MARKET_HOURS_VIOLATION,
                timestamp=timestamp,
                symbol=symbol,
                description=f"Trade outside market hours ({trade_time})",
                severity="warning",
                action_taken="Order queued for market open",
            )
            self.violations.append(violation)
            return False, violation

        return True, None

    def check_daily_loss_limit(
        self,
        daily_pnl: float,
        starting_capital: float,
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        """Check daily loss limit"""

        daily_loss_pct = abs(daily_pnl) / starting_capital if daily_pnl < 0 else 0
        max_daily_loss = self.rules["max_daily_loss_pct"]

        if daily_loss_pct > max_daily_loss:
            violation = ComplianceViolation(
                violation_id=f"DLY_{int(datetime.now().timestamp())}",
                violation_type=ComplianceViolationType.DAILY_LOSS_LIMIT,
                timestamp=datetime.now(),
                symbol="PORTFOLIO",
                description=f"Daily loss {daily_loss_pct*100:.2f}% exceeds {max_daily_loss*100}% limit",
                severity="critical",
                action_taken="Trading halted for remainder of day",
                metadata={"daily_pnl": daily_pnl, "daily_loss_pct": daily_loss_pct},
            )
            self.violations.append(violation)
            return False, violation

        return True, None

    def check_wash_sale(
        self,
        symbol: str,
        recent_trades: List[Dict],
        wash_sale_window_days: int = 30,
    ) -> Tuple[bool, Optional[ComplianceViolation]]:
        """Detect wash sale violations"""

        if not self.rules["wash_sale_detection"]:
            return True, None

        # Check if symbol was sold at a loss in last 30 days
        for trade in recent_trades:
            if (trade.get("symbol") == symbol and trade.get("side") == "sell"
                and trade.get("pnl", 0) < 0):

                trade_date = trade.get("date", datetime.now())
                days_since = (datetime.now() - trade_date).days

                if days_since <= wash_sale_window_days:
                    violation = ComplianceViolation(
                        violation_id=f"WAS_{int(datetime.now().timestamp())}",
                        violation_type=ComplianceViolationType.WASH_SALE,
                        timestamp=datetime.now(),
                        symbol=symbol,
                        description=f"Potential wash sale: repurchase {days_since} days after losing sale",
                        severity="warning",
                        action_taken="Warning issued to user",
                        metadata={"days_since_loss": days_since, "previous_loss": trade.get("pnl")},
                    )
                    self.violations.append(violation)
                    return False, violation

        return True, None

    def get_compliance_report(self) -> Dict:
        """Get compliance report"""
        violations_by_type = {}

        for violation in self.violations:
            vtype = violation.violation_type.value
            if vtype not in violations_by_type:
                violations_by_type[vtype] = 0
            violations_by_type[vtype] += 1

        return {
            "total_violations": len(self.violations),
            "violations_by_type": violations_by_type,
            "critical_violations": len([v for v in self.violations if v.severity == "critical"]),
            "warnings": len([v for v in self.violations if v.severity == "warning"]),
            "violations": [asdict(v) for v in self.violations[-100:]],  # Last 100
        }


class RegulatoryReporter:
    """Generates regulatory reports (SEC 13F, Form 4, etc.)"""

    def __init__(self, fund_name: str):
        self.fund_name = fund_name

    def generate_13f_report(
        self,
        positions: List[Dict],
        reporting_period_end: datetime,
    ) -> RegulatoryReport:
        """Generate SEC 13F report (quarterly holding report)"""

        report_id = f"13F_{reporting_period_end.strftime('%Y%m%d')}"

        return RegulatoryReport(
            report_id=report_id,
            report_date=datetime.now(),
            report_type="13F",
            trades=[],
            positions=positions,
            violations=[],
            summary={
                "fund_name": self.fund_name,
                "reporting_period": reporting_period_end.isoformat(),
                "total_value": sum(p.get("market_value", 0) for p in positions),
                "number_of_holdings": len(positions),
            },
        )

    def generate_trade_report(
        self,
        trades: List[Dict],
        start_date: datetime,
        end_date: datetime,
    ) -> RegulatoryReport:
        """Generate trade execution report"""

        report_id = f"TRD_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"

        return RegulatoryReport(
            report_id=report_id,
            report_date=datetime.now(),
            report_type="Trade Report",
            trades=trades,
            positions=[],
            violations=[],
            summary={
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_trades": len(trades),
                "total_volume": sum(t.get("quantity", 0) for t in trades),
            },
        )

    def export_report_csv(self, report: RegulatoryReport) -> str:
        """Export report as CSV"""
        lines = []

        # Header
        lines.append(f"Report ID,{report.report_id}")
        lines.append(f"Report Type,{report.report_type}")
        lines.append(f"Date,{report.report_date.isoformat()}")
        lines.append("")

        # Positions
        if report.positions:
            lines.append("Symbol,Quantity,Price,Market Value")
            for pos in report.positions:
                lines.append(f"{pos.get('symbol')},{pos.get('quantity')},{pos.get('price')},{pos.get('market_value')}")

        # Trades
        if report.trades:
            lines.append("Symbol,Side,Quantity,Price,Timestamp")
            for trade in report.trades:
                lines.append(
                    f"{trade.get('symbol')},{trade.get('side')},{trade.get('quantity')},{trade.get('price')},{trade.get('timestamp')}"
                )

        return "\n".join(lines)
