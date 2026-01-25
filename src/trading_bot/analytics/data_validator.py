"""Data Validation Module - Detect data quality issues"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum


class DataIssue(Enum):
    """Types of data quality issues"""
    MISSING_DATA = "Missing data points"
    DUPLICATE_DATA = "Duplicate timestamps"
    GAP = "Time gap in data"
    OUTLIER = "Statistical outlier"
    STALE_DATA = "No recent updates"
    NEGATIVE_PRICE = "Negative price"
    ZERO_VOLUME = "Zero volume"
    EXTREME_MOVE = "Extreme price move"
    CROSSED_QUOTES = "Bid > Ask"
    BAD_TICK = "Invalid tick"


@dataclass
class ValidationIssue:
    """Data validation issue"""
    issue_type: DataIssue
    symbol: str
    timestamp: Optional[pd.Timestamp]
    value: float
    details: str
    severity: str  # "warning", "error", "critical"


class DataValidator:
    """Validate market data quality"""
    
    def __init__(self, price_threshold: float = 0.5, 
                 volume_threshold: float = 0.3,
                 zscore_threshold: float = 5.0):
        """
        Args:
            price_threshold: Flag moves > X% as potential bad tick
            volume_threshold: Flag volume changes > X% 
            zscore_threshold: Z-score for outlier detection
        """
        self.price_threshold = price_threshold
        self.volume_threshold = volume_threshold
        self.zscore_threshold = zscore_threshold
        self.issues: List[ValidationIssue] = []
    
    def validate_ohlcv(self, df: pd.DataFrame, symbol: str = "SYMBOL") -> List[ValidationIssue]:
        """Validate OHLCV data
        
        Args:
            df: DataFrame with columns [open, high, low, close, volume]
            symbol: Asset symbol
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if df.empty:
            return issues
        
        # Check for required columns
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.BAD_TICK,
                    symbol=symbol,
                    timestamp=None,
                    value=0,
                    details=f"Missing required column: {col}",
                    severity="error"
                ))
        
        if issues:  # Can't continue without required columns
            return issues
        
        # Check for duplicates
        dup_count = df.index.duplicated().sum()
        if dup_count > 0:
            issues.append(ValidationIssue(
                issue_type=DataIssue.DUPLICATE_DATA,
                symbol=symbol,
                timestamp=None,
                value=dup_count,
                details=f"Found {dup_count} duplicate timestamps",
                severity="warning"
            ))
        
        # Check for missing data
        missing = df.isnull().sum().sum()
        if missing > 0:
            issues.append(ValidationIssue(
                issue_type=DataIssue.MISSING_DATA,
                symbol=symbol,
                timestamp=None,
                value=missing,
                details=f"Found {missing} missing values",
                severity="warning"
            ))
        
        # Check index continuity
        if isinstance(df.index, pd.DatetimeIndex):
            gaps = self._find_time_gaps(df.index)
            for gap_time, gap_hours in gaps:
                if gap_hours > 24:  # Only flag large gaps
                    issues.append(ValidationIssue(
                        issue_type=DataIssue.GAP,
                        symbol=symbol,
                        timestamp=gap_time,
                        value=gap_hours,
                        details=f"Time gap of {gap_hours:.1f} hours",
                        severity="warning"
                    ))
        
        # Validate OHLC relationships
        for idx, row in df.iterrows():
            if row["high"] < row["low"]:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.BAD_TICK,
                    symbol=symbol,
                    timestamp=idx,
                    value=row["high"],
                    details=f"High ({row['high']}) < Low ({row['low']})",
                    severity="error"
                ))
            
            if row["open"] > row["high"] or row["open"] < row["low"]:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.BAD_TICK,
                    symbol=symbol,
                    timestamp=idx,
                    value=row["open"],
                    details=f"Open outside high-low range",
                    severity="warning"
                ))
            
            if row["close"] > row["high"] or row["close"] < row["low"]:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.BAD_TICK,
                    symbol=symbol,
                    timestamp=idx,
                    value=row["close"],
                    details=f"Close outside high-low range",
                    severity="warning"
                ))
            
            # Check for negative/zero prices
            if row["close"] <= 0:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.NEGATIVE_PRICE,
                    symbol=symbol,
                    timestamp=idx,
                    value=row["close"],
                    details=f"Invalid price: {row['close']}",
                    severity="error"
                ))
            
            # Check for zero volume
            if row["volume"] == 0:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.ZERO_VOLUME,
                    symbol=symbol,
                    timestamp=idx,
                    value=0,
                    details="Zero volume",
                    severity="warning"
                ))
        
        # Check for price outliers (extreme moves)
        returns = df["close"].pct_change()
        mean_return = returns.mean()
        std_return = returns.std()
        
        for idx, ret in returns.items():
            if std_return > 0:
                zscore = (ret - mean_return) / std_return
                if abs(zscore) > self.zscore_threshold:
                    issues.append(ValidationIssue(
                        issue_type=DataIssue.EXTREME_MOVE,
                        symbol=symbol,
                        timestamp=idx,
                        value=ret * 100,
                        details=f"Extreme move: {ret*100:.2f}% (zscore: {zscore:.1f})",
                        severity="warning"
                    ))
        
        # Check for volume outliers
        vol = df["volume"]
        if len(vol) > 1 and vol.std() > 0:
            z_vol = np.abs((vol - vol.mean()) / vol.std())
            outlier_idx = z_vol[z_vol > self.zscore_threshold].index
            for idx in outlier_idx:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.OUTLIER,
                    symbol=symbol,
                    timestamp=idx,
                    value=vol[idx],
                    details=f"Extreme volume: {vol[idx]:.0f}",
                    severity="warning"
                ))
        
        self.issues.extend(issues)
        return issues
    
    def validate_ticks(self, df: pd.DataFrame, symbol: str = "SYMBOL") -> List[ValidationIssue]:
        """Validate tick data with bid/ask
        
        Args:
            df: DataFrame with columns [bid, ask, bid_size, ask_size]
            symbol: Asset symbol
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if df.empty or "bid" not in df.columns or "ask" not in df.columns:
            return issues
        
        for idx, row in df.iterrows():
            # Check crossed quotes
            if row["bid"] > row["ask"]:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.CROSSED_QUOTES,
                    symbol=symbol,
                    timestamp=idx,
                    value=row["bid"],
                    details=f"Bid ({row['bid']}) > Ask ({row['ask']})",
                    severity="warning"
                ))
            
            # Check for negative prices
            if row["bid"] <= 0 or row["ask"] <= 0:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.NEGATIVE_PRICE,
                    symbol=symbol,
                    timestamp=idx,
                    value=row["bid"],
                    details="Negative bid/ask",
                    severity="error"
                ))
        
        self.issues.extend(issues)
        return issues
    
    def validate_prices(self, prices: Dict[str, float]) -> List[ValidationIssue]:
        """Validate real-time price data
        
        Args:
            prices: Dict of {symbol: price}
            
        Returns:
            List of validation issues
        """
        issues = []
        
        for symbol, price in prices.items():
            if price <= 0:
                issues.append(ValidationIssue(
                    issue_type=DataIssue.NEGATIVE_PRICE,
                    symbol=symbol,
                    timestamp=pd.Timestamp.now(),
                    value=price,
                    details=f"Invalid price: {price}",
                    severity="error"
                ))
            
            if np.isnan(price) or np.isinf(price):
                issues.append(ValidationIssue(
                    issue_type=DataIssue.BAD_TICK,
                    symbol=symbol,
                    timestamp=pd.Timestamp.now(),
                    value=price,
                    details=f"Invalid numeric value: {price}",
                    severity="error"
                ))
        
        self.issues.extend(issues)
        return issues
    
    def validate_freshness(self, df: pd.DataFrame, symbol: str = "SYMBOL",
                          max_age_minutes: int = 60) -> List[ValidationIssue]:
        """Check if data is recent
        
        Args:
            df: DataFrame with datetime index
            symbol: Asset symbol
            max_age_minutes: Maximum allowed age
            
        Returns:
            List of validation issues
        """
        issues = []
        
        if df.empty or not isinstance(df.index, pd.DatetimeIndex):
            return issues
        
        last_update = df.index[-1]
        age = pd.Timestamp.now() - last_update
        age_minutes = age.total_seconds() / 60
        
        if age_minutes > max_age_minutes:
            issues.append(ValidationIssue(
                issue_type=DataIssue.STALE_DATA,
                symbol=symbol,
                timestamp=last_update,
                value=age_minutes,
                details=f"Data is {age_minutes:.0f} minutes old",
                severity="warning"
            ))
        
        self.issues.extend(issues)
        return issues
    
    def _find_time_gaps(self, index: pd.DatetimeIndex, 
                       expected_freq: Optional[str] = None) -> List[Tuple[pd.Timestamp, float]]:
        """Find gaps in time series index
        
        Returns:
            List of (gap_timestamp, gap_hours)
        """
        if len(index) < 2:
            return []
        
        gaps = []
        for i in range(1, len(index)):
            delta = index[i] - index[i-1]
            
            # Detect if gap is larger than expected
            if expected_freq is None:
                # Use median of differences as expected
                deltas = index.to_series().diff()
                expected_delta = deltas.median()
            else:
                expected_delta = pd.Timedelta(expected_freq)
            
            if delta > expected_delta * 2:  # 2x normal is a gap
                gap_hours = delta.total_seconds() / 3600
                gaps.append((index[i], gap_hours))
        
        return gaps
    
    def get_summary(self) -> Dict:
        """Get validation summary"""
        if not self.issues:
            return {"total_issues": 0, "by_type": {}, "by_severity": {}}
        
        by_type = {}
        by_severity = {}
        
        for issue in self.issues:
            # Count by type
            type_name = issue.issue_type.name
            by_type[type_name] = by_type.get(type_name, 0) + 1
            
            # Count by severity
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1
        
        return {
            "total_issues": len(self.issues),
            "critical_count": by_severity.get("critical", 0),
            "error_count": by_severity.get("error", 0),
            "warning_count": by_severity.get("warning", 0),
            "by_type": by_type,
            "by_severity": by_severity
        }
    
    def get_issues_for_symbol(self, symbol: str) -> List[ValidationIssue]:
        """Get all issues for a specific symbol"""
        return [i for i in self.issues if i.symbol == symbol]
    
    def has_critical_issues(self) -> bool:
        """Check if any critical issues exist"""
        return any(i.severity == "critical" for i in self.issues)
    
    def has_errors(self) -> bool:
        """Check if any errors exist"""
        return any(i.severity in ["error", "critical"] for i in self.issues)
    
    def clear(self) -> None:
        """Clear all issues"""
        self.issues.clear()
