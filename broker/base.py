"""
Abstract Broker — defines the interface for order execution and account management.

Concrete implementations:
    AlpacaBroker     — wraps alpaca.trading.TradingClient (US stocks)
    CNPaperBroker    — in-memory simulation with A-share rules (paper trading)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AccountInfo:
    """Standardized account snapshot."""
    buying_power: float
    cash: float
    portfolio_value: float
    currency: str
    status: str = "ACTIVE"


@dataclass
class Position:
    """Standardized position record."""
    symbol: str
    qty: float
    market_value: float
    current_price: float
    cost_basis: Optional[float] = None


@dataclass
class OrderResult:
    """Standardized order result."""
    symbol: str
    status: str            # "filled", "rejected", "failed", "submitted"
    qty: float
    side: str              # "buy" or "sell"
    filled_price: Optional[float] = None
    error: Optional[str] = None
    order_id: Optional[str] = None
    order_type: str = "market"
    timestamp: datetime = field(default_factory=datetime.now)


class Broker(ABC):
    """Abstract broker interface for order execution and account management."""

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Return current account information."""
        ...

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Return all current open positions."""
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> OrderResult:
        """Place an order and return the result."""
        ...

    @abstractmethod
    def cancel_all_orders(self) -> List[Dict[str, Any]]:
        """Cancel all pending orders."""
        ...

    @abstractmethod
    def get_order_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent order history."""
        ...

    def get_position_value(self, symbol: str) -> float:
        """Get market value of a specific position (convenience)."""
        for p in self.get_positions():
            if p.symbol == symbol:
                return p.market_value
        return 0.0
