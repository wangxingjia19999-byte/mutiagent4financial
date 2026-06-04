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
    market: str = "us",
) -> List[str]:
    """
    Get a list of tradeable stock symbols.

    Args:
        scope: one of:
            US: "all", "liquid", "sp500", "nasdaq100"
            CN: "all_cn", "liquid_cn", "csi300", "csi500"
        market: "us" (default) or "cn"
        apply_filters: If True, filter by price/volume after fetching.

    Returns:
        List of symbol strings.
    """
    if market == "cn":
        return _get_cn_market_universe(scope)

    # ── US path (existing) ──
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


# ────────────────────────────────────────────────────────────────
# A-Share Market Universe (via Tushare)
# ────────────────────────────────────────────────────────────────

_CN_UNIVERSE_CACHE: Optional[List[str]] = None


def _get_cn_market_universe(scope: str = "liquid_cn") -> List[str]:
    """Get A-share stock universe from Tushare."""
    global _CN_UNIVERSE_CACHE

    try:
        from data.providers.tushare_provider import TushareProvider

        provider = TushareProvider()
        symbols = provider.get_universe(scope=scope, apply_filters=True)
        if symbols:
            _CN_UNIVERSE_CACHE = symbols
            logger.info("A-share universe: %d symbols (scope=%s)", len(symbols), scope)
            return symbols
    except ImportError as e:
        logger.warning("TushareProvider not available: %s", e)
    except Exception as e:
        logger.warning("A-share universe fetch failed: %s", e)

    # Fallback: use cached symbols or empty list
    if _CN_UNIVERSE_CACHE:
        logger.info("Using cached A-share universe: %d symbols", len(_CN_UNIVERSE_CACHE))
        return _apply_scope_cap(_CN_UNIVERSE_CACHE, scope)

    # Last resort: return a minimal set of well-known A-shares
    fallback = [
        "000001.SZ", "000002.SZ", "000858.SZ", "002415.SZ", "300750.SZ",
        "600000.SH", "600036.SH", "600276.SH", "600519.SH", "601318.SH",
        "000333.SZ", "002594.SZ", "300059.SZ", "600900.SH", "601166.SH",
        "000651.SZ", "002142.SZ", "300124.SZ", "600030.SH", "601398.SH",
        "000725.SZ", "002475.SZ", "300760.SZ", "600585.SH", "601899.SH",
        "000063.SZ", "002714.SZ", "300498.SZ", "600809.SH", "603288.SH",
    ]
    return _apply_scope_cap(sorted(fallback), scope)


def _apply_scope_cap(symbols: List[str], scope: str) -> List[str]:
    """Apply scope-based truncation."""
    caps = {
        "csi300": 300,
        "csi500": 500,
        "liquid_cn": 2000,
        "all_cn": len(symbols),
    }
    cap = caps.get(scope, len(symbols))
    return sorted(symbols)[:cap]


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
    market: str = "us",
) -> List[str]:
    """
    Get market universe with disk caching (avoid repeated API calls).

    Args:
        market: "us" or "cn"
        max_age_hours: Re-fetch if cache is older than this.
    """
    # Separate cache files for US and CN
    cache_file = _CACHE_FILE.parent / f"market_universe_{market}.txt"

    if cache_file.exists():
        age_seconds = time.time() - cache_file.stat().st_mtime
        if age_seconds < max_age_hours * 3600:
            try:
                content = cache_file.read_text().strip()
                if content:
                    cached = [s.strip() for s in content.splitlines() if s.strip()]
                    if cached:
                        # Scope-based truncation
                        scope_caps = {
                            "nasdaq100": 100, "sp500": 500, "liquid": 2000,
                            "csi300": 300, "csi500": 500, "liquid_cn": 2000,
                            "all": len(cached), "all_cn": len(cached),
                        }
                        cap = scope_caps.get(scope, len(cached))
                        return cached[:cap]
            except Exception:
                pass

    symbols = get_market_universe(
        scope=scope, api_key=api_key, secret_key=secret_key,
        apply_filters=apply_filters, market=market,
    )
    if symbols:
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text("\n".join(symbols))
        except Exception:
            pass
    return symbols
