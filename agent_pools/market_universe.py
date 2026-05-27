"""
Market Universe — fetch all tradeable US stocks from Alpaca with filtering.

Usage:
    from agent_pools.market_universe import get_market_universe

    symbols = get_market_universe("all")        # all tradeable stocks
    symbols = get_market_universe("sp500")      # S&P 500-like (top market cap)
    symbols = get_market_universe("nasdaq100")  # NASDAQ 100-like
    symbols = get_market_universe("liquid")     # liquid stocks only (volume filter)
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import List, Set, Optional

logger = logging.getLogger("MarketUniverse")

_project_root = Path(__file__).resolve().parents[1]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetAssetsRequest
    from alpaca.trading.enums import AssetClass, AssetStatus
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False


# ---------------------------------------------------------------
# Filtering defaults (configurable)
# ---------------------------------------------------------------
MIN_PRICE       = 2.0        # minimum share price
MIN_VOLUME      = 100_000    # minimum avg daily volume
MAX_PRICE       = 5_000.0    # skip ultra-expensive stocks (Berkshire A etc)
EXCLUDE_EXCHANGES = {"OTC", "OTCBB", "PINK"}  # skip OTC / penny exchanges


def _is_desired_exchange(exchange: str) -> bool:
    if not exchange:
        return False
    return exchange.upper() not in EXCLUDE_EXCHANGES


def fetch_alpaca_assets(api_key: str = None, secret_key: str = None) -> List[dict]:
    """
    Fetch ALL tradeable US equity assets from Alpaca.
    Returns a list of {symbol, name, exchange, tradable, ...} dicts.
    """
    api_key = api_key or os.getenv("ALPACA_API_KEY")
    secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

    if not ALPACA_AVAILABLE or not api_key:
        logger.warning("Alpaca SDK unavailable — returning empty universe")
        return []

    client = TradingClient(api_key, secret_key)
    req = GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
    assets = client.get_all_assets(req)

    results = []
    for a in assets:
        results.append({
            "symbol": a.symbol,
            "name": a.name or "",
            "exchange": a.exchange or "",
            "tradable": bool(a.tradable),
            "easy_to_borrow": bool(a.easy_to_borrow),
            "shortable": bool(a.shortable),
            "fractionable": bool(a.fractionable),
        })
    return results


def filter_by_volume_and_price(
    symbols: List[str],
    api_key: str = None,
    secret_key: str = None,
    min_price: float = MIN_PRICE,
    min_volume: float = MIN_VOLUME,
    max_price: float = MAX_PRICE,
) -> List[str]:
    """
    Use Alpaca snapshot/latest-quote data to filter by price and volume.
    Falls back gracefully when data is unavailable.
    """
    api_key = api_key or os.getenv("ALPACA_API_KEY")
    secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

    if not symbols:
        return []

    try:
        from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest, StockSnapshotRequest
        from alpaca.data.historical import StockHistoricalDataClient
    except ImportError:
        logger.warning("alpaca-py data client unavailable — skipping price/volume filter")
        return symbols

    if not api_key:
        logger.warning("No Alpaca key — skipping price/volume filter")
        return symbols

    data_client = StockHistoricalDataClient(api_key, secret_key)
    passed: List[str] = []

    # Process in batches of 500 (Alpaca limit)
    batch_size = 500
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            snap_req = StockSnapshotRequest(symbol_or_symbols=batch)
            snapshots = data_client.get_stock_snapshot(snap_req)

            for sym, snap in (snapshots or {}).items():
                price = getattr(snap, 'daily_bar', None)
                trade = getattr(snap, 'latest_trade', None)
                bar = getattr(snap, 'daily_bar', None)

                # Extract price
                p = 0.0
                if trade and getattr(trade, 'price', 0):
                    p = float(trade.price)
                elif bar and getattr(bar, 'close', 0):
                    p = float(bar.close)

                # Extract volume
                v = 0.0
                if bar and getattr(bar, 'volume', 0):
                    v = float(bar.volume)

                if p <= 0 or v <= 0:
                    # No snapshot data — keep it (conservative)
                    passed.append(sym)
                elif min_price <= p <= max_price and v >= min_volume:
                    passed.append(sym)
                # else: filtered out

        except Exception as e:
            logger.warning("Snapshot batch %d–%d failed: %s — keeping all in batch", i, i + len(batch), e)
            passed.extend(batch)

        time.sleep(0.15)  # rate-limit courtesy

    logger.info("Price/volume filter: %d -> %d symbols passed", len(symbols), len(passed))
    return passed


def get_market_universe(
    scope: str = "liquid",
    api_key: str = None,
    secret_key: str = None,
    apply_filters: bool = True,
) -> List[str]:
    """
    Get a list of tradeable US stock symbols.

    Args:
        scope: one of:
            "all"     — every tradeable equity
            "liquid"  — top ~2000 liquid stocks (price, volume filtered)
            "sp500"   — top ~500 liquid stocks
            "nasdaq100" — top ~100 liquid stocks
        apply_filters: If True, filter by price/volume after fetching.

    Returns:
        List of symbol strings.
    """
    assets = fetch_alpaca_assets(api_key=api_key, secret_key=secret_key)

    if not assets:
        logger.warning("No assets from Alpaca — returning empty list")
        return []

    # Pre-filter: tradable + desired exchange
    candidates = [
        a["symbol"] for a in assets
        if a["tradable"] and _is_desired_exchange(a.get("exchange", ""))
    ]

    logger.info("Alpaca universe: %d tradable on major exchanges (from %d total)",
                len(candidates), len(assets))

    if apply_filters:
        candidates = filter_by_volume_and_price(
            candidates, api_key=api_key, secret_key=secret_key
        )

    # Scope caps (sorted alphabetically for reproducibility)
    candidates = sorted(candidates)

    if scope == "nasdaq100":
        return candidates[:100]
    elif scope == "sp500":
        return candidates[:500]
    elif scope == "liquid":
        return candidates[:2000]
    else:  # "all"
        return candidates


# ---------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------
_CACHE_FILE = _project_root / "data" / "cache" / "market_universe.txt"


def load_cached_symbols() -> Optional[List[str]]:
    """Load previously cached universe symbols."""
    if _CACHE_FILE.exists():
        content = _CACHE_FILE.read_text().strip()
        if content:
            return [s.strip() for s in content.splitlines() if s.strip()]
    return None


def save_cached_symbols(symbols: List[str]) -> None:
    """Cache universe symbols to disk."""
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text("\n".join(symbols))


def get_market_universe_cached(
    scope: str = "liquid",
    api_key: str = None,
    secret_key: str = None,
    max_age_hours: int = 24,
    apply_filters: bool = True,
) -> List[str]:
    """
    Get market universe with disk caching (avoid repeated Alpaca API calls).

    Args:
        max_age_hours: Re-fetch if cache is older than this.
    """
    if _CACHE_FILE.exists():
        age_seconds = time.time() - _CACHE_FILE.stat().st_mtime
        if age_seconds < max_age_hours * 3600:
            cached = load_cached_symbols()
            if cached:
                # Scope-based truncation on cached list
                if scope == "nasdaq100":
                    return cached[:100]
                elif scope == "sp500":
                    return cached[:500]
                elif scope == "liquid":
                    return cached[:2000]
                return cached

    symbols = get_market_universe(
        scope=scope, api_key=api_key, secret_key=secret_key, apply_filters=apply_filters
    )
    if symbols:
        save_cached_symbols(symbols)
    return symbols
