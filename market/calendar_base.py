"""
Abstract MarketCalendar — defines the interface for market-hours checking.

Concrete implementations:
    USMarketCalendar  — US Eastern 9:30-16:00
    CNMarketCalendar  — China CST 9:30-11:30, 13:00-15:00
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class MarketCalendar(ABC):
    """Abstract calendar for checking trading hours and holidays."""

    @abstractmethod
    def is_open(self, dt: Optional[datetime] = None) -> bool:
        """Return True if the market is open at the given time (default: now)."""
        ...

    @abstractmethod
    def status_str(self, dt: Optional[datetime] = None) -> str:
        """Return a human-readable market status string."""
        ...

    def next_open(self, dt: Optional[datetime] = None) -> datetime:
        """Return the next time the market opens. Default: next session start."""
        return (dt or datetime.now()).replace(hour=9, minute=30, second=0, microsecond=0)
