"""
US Market Calendar — extracted from execution_agent.py.

US Eastern Time: 9:30 AM – 4:00 PM, Monday–Friday.
Rough DST detection: April–October = EDT (UTC-4), November–March = EST (UTC-5).
"""

from datetime import datetime, time
from .calendar_base import MarketCalendar


class USMarketCalendar(MarketCalendar):
    """US stock market hours (Eastern Time)."""

    OPEN_TIME = time(9, 30)
    CLOSE_TIME = time(16, 0)

    def _et_hour(self, dt: datetime) -> int:
        """Convert UTC hour to approximate Eastern hour."""
        month = dt.month
        is_dst = 3 < month < 11  # rough DST: April–October
        offset = 4 if is_dst else 5
        return (dt.hour - offset + 24) % 24

    def is_open(self, dt: datetime = None) -> bool:
        dt = dt or datetime.utcnow()
        if dt.weekday() >= 5:  # Saturday or Sunday
            return False
        et_hour = self._et_hour(dt)
        current = time(et_hour, dt.minute)
        return self.OPEN_TIME <= current <= self.CLOSE_TIME

    def status_str(self, dt: datetime = None) -> str:
        if self.is_open(dt):
            return "OPEN"
        dt = dt or datetime.utcnow()
        if dt.weekday() >= 5:
            return "CLOSED (WEEKEND)"
        return "CLOSED (OUTSIDE TRADING HOURS)"
