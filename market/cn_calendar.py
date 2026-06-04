"""
China A-Share Market Calendar.

Trading hours (CST / UTC+8):
    Morning:  09:30 – 11:30
    Afternoon: 13:00 – 15:00
    Lunch break: 11:30 – 13:00 (market closed)

Holidays are loaded from a simple CSV file (market/cn_holidays.csv) that lists
non-trading weekdays, one date per line in YYYY-MM-DD format.
"""

import os
from datetime import datetime, time, date, timedelta
from pathlib import Path
from typing import Set

from .calendar_base import MarketCalendar


def _load_holiday_dates() -> Set[date]:
    """Load CN market holidays from a CSV file.

    Format: one date per line, YYYY-MM-DD
    Comments (#) and blank lines are ignored.
    """
    holidays: Set[date] = set()

    # Try to load from the same directory
    csv_path = Path(__file__).parent / "cn_holidays.csv"
    if not csv_path.exists():
        return holidays

    try:
        for line in csv_path.read_text().strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                holidays.add(datetime.strptime(line, "%Y-%m-%d").date())
            except ValueError:
                continue
    except Exception:
        pass

    return holidays


class CNMarketCalendar(MarketCalendar):
    """A-share market hours (China Standard Time, UTC+8)."""

    MORNING_OPEN = time(9, 30)
    MORNING_CLOSE = time(11, 30)
    AFTERNOON_OPEN = time(13, 0)
    AFTERNOON_CLOSE = time(15, 0)

    # Pre-market call auction: 9:15 – 9:25 (not treated as trading time)

    def __init__(self):
        self._holidays = _load_holiday_dates()

    def _now_cst(self, dt: datetime = None) -> datetime:
        """Get current time in CST (approximation: UTC+8)."""
        import datetime as dt_mod
        if dt is None:
            # Use system local time or UTC conversion
            utc_now = dt_mod.datetime.utcnow()
            return utc_now + timedelta(hours=8)
        # Assume dt is already in CST or UTC — if hour < 0 mod 24 resolution needed
        return dt

    def is_weekday(self, dt: datetime = None) -> bool:
        dt = dt or datetime.now()
        # Convert UTC to CST weekday
        # Simple approach: use local time if system is in CST,
        # otherwise approximate UTC+8
        return dt.weekday() < 5

    def is_holiday(self, dt: datetime = None) -> bool:
        if dt is None:
            dt = datetime.now()
        return dt.date() in self._holidays

    def is_open(self, dt: datetime = None) -> bool:
        if dt is None:
            dt = datetime.now()

        if not self.is_weekday(dt):
            return False

        if self.is_holiday(dt):
            return False

        t = dt.time()
        morning = self.MORNING_OPEN <= t <= self.MORNING_CLOSE
        afternoon = self.AFTERNOON_OPEN <= t <= self.AFTERNOON_CLOSE
        return morning or afternoon

    def status_str(self, dt: datetime = None) -> str:
        if dt is None:
            dt = datetime.now()

        if not self.is_weekday(dt):
            return "CLOSED (WEEKEND)"
        if self.is_holiday(dt):
            return "CLOSED (HOLIDAY)"

        t = dt.time()
        if t < self.MORNING_OPEN:
            return "CLOSED (BEFORE OPEN)"
        if self.MORNING_CLOSE < t < self.AFTERNOON_OPEN:
            return "CLOSED (LUNCH BREAK)"
        if t > self.AFTERNOON_CLOSE:
            return "CLOSED (AFTER HOURS)"

        if self.MORNING_OPEN <= t <= self.MORNING_CLOSE:
            return "OPEN (MORNING SESSION)"
        return "OPEN (AFTERNOON SESSION)"
