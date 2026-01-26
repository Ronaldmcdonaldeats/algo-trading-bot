"""Smart order execution using limit orders for better fills."""

from dataclasses import dataclass
from enum import Enum
import pandas as pd


class OrderType(Enum):
    """Order type options."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SMART = "SMART"  # Chooses limit vs market based on conditions


@dataclass
class ExecutionConfig:
    """Configuration for smart order execution."""
    use_limit_orders: bool = True
    limit_offset_pct: float = 0.2  # 0.2% inside spread for better fills
    smart_mode_threshold_bps: float = 50.0  # Use limit if spread > 50 bps
    limit_order_timeout_seconds: int = 30  # If limit order not filled, use market
    max_spread_pct: float = 1.0  # Reject order if spread > 1%
    volume_check_enabled: bool = True
    min_volume_threshold: float = 100_000.0  # Minimum $ volume to support limit orders


class OrderExecution:
    """Smart order execution strategy using limit orders."""
    
    @staticmethod
    def calculate_limit_price(
        current_price: float,
        side: str,
        spread_pct: float = 0.1,
        limit_offset_pct: float = 0.2,
    ) -> float:
        """Calculate limit price inside the spread for better execution.
        
        Args:
            current_price: Current market price
            side: "BUY" or "SELL"
            spread_pct: Current bid-ask spread as percentage
            limit_offset_pct: How far inside spread to place limit (0.2% = inside 20% of spread)
            
        Returns:
            Limit price offset inside the spread
            
        Example:
            Current price: $100, spread: 0.10% (10 cents)
            For BUY: limit = $100 - (0.10% * 0.2) = $99.98 (buy at $99.98 vs market $100)
            For SELL: limit = $100 + (0.10% * 0.2) = $100.02 (sell at $100.02 vs market $100)
        """
        spread_offset = current_price * (spread_pct / 100.0) * (limit_offset_pct / 100.0)
        
        if side == "BUY":
            # Buy limit is below market, so we save money
            limit_price = current_price - spread_offset
        else:  # SELL
            # Sell limit is above market, so we get more
            limit_price = current_price + spread_offset
        
        return round(limit_price, 2)

    @staticmethod
    def should_use_limit_order(
        spread_bps: float,
        volume_dollars: float,
        config: ExecutionConfig | None = None,
    ) -> bool:
        """Determine if limit order should be used instead of market order.
        
        Args:
            spread_bps: Bid-ask spread in basis points (1 bps = 0.01%)
            volume_dollars: Recent trading volume in dollars (1-min average)
            config: Execution configuration
            
        Returns:
            True if limit order recommended, False if market order recommended
            
        Logic:
        - If spread is tight (<50 bps), market order is fine
        - If spread is wide (>50 bps), use limit to avoid slippage
        - If volume is low, use market to ensure fill
        """
        if config is None:
            config = ExecutionConfig()
        
        if not config.use_limit_orders:
            return False
        
        # If spread is very wide (>1%), reject order
        if spread_bps > (config.max_spread_pct * 100):
            return False  # Don't trade in illiquid conditions
        
        # If volume too low and enabled, use market order for guaranteed fill
        if config.volume_check_enabled and volume_dollars < config.min_volume_threshold:
            return False
        
        # Use limit order if spread is wide enough to justify
        return spread_bps > config.smart_mode_threshold_bps

    @staticmethod
    def estimate_execution_cost(
        qty: int,
        current_price: float,
        spread_pct: float,
        commission_bps: float = 10.0,
        use_limit: bool = True,
        limit_offset_pct: float = 0.2,
    ) -> dict:
        """Estimate cost of buying/selling with limit vs market orders.
        
        Args:
            qty: Order quantity
            current_price: Current market price
            spread_pct: Bid-ask spread as percentage
            commission_bps: Commission in basis points
            use_limit: Whether to use limit order
            limit_offset_pct: Limit order offset inside spread
            
        Returns:
            Dict with:
            - market_cost: Cost using market order
            - limit_cost: Cost using limit order
            - savings: How much limit order saves
            - savings_pct: Savings as percentage
        """
        notional = qty * current_price
        
        # Market order: pay full spread
        spread_amount = notional * (spread_pct / 100.0)
        commission_amount = notional * (commission_bps / 10_000.0)
        market_cost = spread_amount + commission_amount
        
        # Limit order: pay only partial spread + commission
        spread_offset = notional * (spread_pct / 100.0) * (limit_offset_pct / 100.0)
        limit_cost = spread_offset + commission_amount
        
        savings = market_cost - limit_cost
        savings_pct = (savings / market_cost * 100.0) if market_cost > 0 else 0
        
        return {
            "notional": notional,
            "market_cost": round(market_cost, 2),
            "limit_cost": round(limit_cost, 2),
            "savings": round(savings, 2),
            "savings_pct": round(savings_pct, 2),
        }

    @staticmethod
    def estimate_spread_from_volume(volume_series: pd.Series) -> float:
        """Estimate spread from volume data.
        
        Args:
            volume_series: Series of recent volume data points
            
        Returns:
            Estimated spread as percentage (e.g., 0.1 = 0.1%)
            
        Logic:
        - High volume = tight spread
        - Low volume = wide spread
        - Typical stock: 5-10M shares/day = 0.05-0.1% spread
        """
        if volume_series.empty:
            return 0.1  # Default 0.1% spread
        
        try:
            avg_volume = float(volume_series.mean())
        except (TypeError, ValueError):
            return 0.1  # Default if can't compute mean
        
        if avg_volume <= 0:
            return 0.1  # Default 0.1% spread
        
        if avg_volume > 10_000_000:  # Very liquid
            spread_pct = 0.05
        elif avg_volume > 1_000_000:  # Liquid
            spread_pct = 0.1
        elif avg_volume > 100_000:  # Normal
            spread_pct = 0.2
        else:  # Illiquid
            spread_pct = 0.5
        
        return spread_pct

    @staticmethod
    def get_order_type(
        current_price: float,
        side: str,
        qty: int,
        volume_data: pd.Series | None = None,
        spread_estimate_pct: float = 0.1,
        config: ExecutionConfig | None = None,
    ) -> dict:
        """Get recommended order type and parameters.
        
        Args:
            current_price: Current market price
            side: "BUY" or "SELL"
            qty: Order quantity
            volume_data: Recent volume data (optional)
            spread_estimate_pct: Estimated spread percentage
            config: Execution configuration
            
        Returns:
            Dict with:
            - type: "MARKET" or "LIMIT"
            - limit_price: Limit price (if using limit order)
            - rationale: Why this order type was chosen
            - expected_savings: Expected $ savings vs market
        """
        if config is None:
            config = ExecutionConfig()
        
        # Convert spread % to bps for decision logic
        spread_bps = spread_estimate_pct * 100
        
        # Estimate volume if not provided
        volume_dollars = 1_000_000  # Conservative estimate
        if volume_data is not None and not volume_data.empty:
            try:
                mean_vol = volume_data.mean()
                avg_vol = float(mean_vol) if not isinstance(mean_vol, pd.Series) else float(mean_vol.iloc[0])
                volume_dollars = float(avg_vol * float(current_price))
            except (TypeError, ValueError, AttributeError):
                pass  # Use conservative estimate
        
        use_limit = OrderExecution.should_use_limit_order(
            spread_bps=spread_bps,
            volume_dollars=volume_dollars,
            config=config,
        )
        
        result = {
            "type": "LIMIT" if use_limit else "MARKET",
            "side": side,
            "qty": qty,
            "limit_price": None,
            "rationale": "",
            "expected_savings": 0,
        }
        
        if use_limit:
            limit_price = OrderExecution.calculate_limit_price(
                current_price=current_price,
                side=side,
                spread_pct=spread_estimate_pct,
                limit_offset_pct=config.limit_offset_pct,
            )
            result["limit_price"] = limit_price
            result["rationale"] = f"Wide spread ({spread_bps:.0f} bps), using limit for better fill"
            
            # Calculate expected savings
            cost_analysis = OrderExecution.estimate_execution_cost(
                qty=qty,
                current_price=current_price,
                spread_pct=spread_estimate_pct,
                use_limit=True,
                limit_offset_pct=config.limit_offset_pct,
            )
            result["expected_savings"] = cost_analysis["savings"]
        else:
            if spread_bps < config.smart_mode_threshold_bps:
                result["rationale"] = f"Tight spread ({spread_bps:.0f} bps), market order is fine"
            else:
                result["rationale"] = f"Low volume, using market for guaranteed fill"
        
        return result
