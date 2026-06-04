"""
Market Configuration — defines market-specific parameters for US and CN markets.

All market-dependent logic should reference a MarketConfig instance rather than
hardcoding currency symbols, lot sizes, price limits, etc.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MarketConfig:
    """Immutable market configuration. Create once, pass everywhere."""

    code: str                # "us" or "cn"
    currency: str            # "USD" or "CNY"
    currency_symbol: str     # "$" or "¥"
    lot_size: int            # 1 (US fractional) or 100 (CN board lot)
    price_limit_pct: Optional[float]  # None (no limit) or 0.10 (CN ±10%)
    settlement: str          # "T+0" or "T+1"
    timezone: str            # "US/Eastern" or "Asia/Shanghai"
    price_decimals: int      # decimal places for price display
    market_name: str         # human-readable name
    trading_days_per_year: int = 252  # approximate, used for annualization
    min_commission: float = 5.0       # minimum commission per trade
    stamp_duty_sell: float = 0.0      # stamp duty on sell side (CN: 0.0005)


# Pre-built instances
US_MARKET = MarketConfig(
    code="us",
    currency="USD",
    currency_symbol="$",
    lot_size=1,
    price_limit_pct=None,       # no daily price limit
    settlement="T+0",
    timezone="US/Eastern",
    price_decimals=2,
    market_name="US Stocks",
    trading_days_per_year=252,
    min_commission=0.0,
    stamp_duty_sell=0.0,
)

CN_MARKET = MarketConfig(
    code="cn",
    currency="CNY",
    currency_symbol="¥",
    lot_size=100,
    price_limit_pct=0.10,       # ±10% for main board stocks
    settlement="T+1",
    timezone="Asia/Shanghai",
    price_decimals=2,
    market_name="A-Share (China)",
    trading_days_per_year=244,  # Chinese market has ~244 trading days
    min_commission=5.0,         # minimum ¥5 per trade
    stamp_duty_sell=0.0005,     # 0.05% stamp duty on sells
)
