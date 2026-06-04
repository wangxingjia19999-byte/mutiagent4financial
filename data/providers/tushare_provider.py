"""
Tushare DataProvider — implements DataProvider for A-share stocks via Tushare API.

Data mapping (Tushare → universal format):
    trade_date (str YYYYMMDD) → date (pd.Timestamp)
    ts_code    (str 000001.SZ) → symbol
    vol        (float, shares) → volume
    open, high, low, close    → same (1:1)
"""

import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .base import DataProvider
from .mock_provider import MockProvider

logger = logging.getLogger("TushareProvider")

# ── A-share filtering defaults ─────────────────────────────────────
CN_MIN_PRICE = 2.0         # minimum share price (CNY)
CN_MIN_VOLUME = 100_000    # minimum volume (shares)
CN_MAX_PRICE = 3_000.0     # skip ultra-expensive stocks
CN_EXCLUDE_STATUS = {"D", "P"}  # exclude 退市 (D), 暂停上市 (P)

# ── Scope presets ──────────────────────────────────────────────────
# CSI 300 and CSI 500 constituent lists (approximate, updated periodically)
CSI300_SYMBOLS = None       # loaded lazily
CSI500_SYMBOLS = None


def _ts_code_to_symbol(ts_code: str) -> str:
    """Normalize Tushare ts_code to standard format (e.g. '000001.SZ')."""
    return ts_code.strip().upper()


class TushareProvider(DataProvider):
    """A-share market data via Tushare, with mock fallback."""

    def __init__(self, token: str = None, cache_dir: str = None):
        token = token or os.getenv("TUSHARE_TOKEN", "")
        if not token or token.startswith("os.getenv"):
            logger.warning("TUSHARE_TOKEN not set — using mock data for A-shares")
            self._pro = None
            self._mock = MockProvider()
            return

        try:
            import tushare as ts
            ts.set_token(token)
            self._pro = ts.pro_api()
            self._mock = None
            # Quick connectivity check
            self._pro.query("stock_basic", exchange="", list_status="L", fields="ts_code", limit=1)
            logger.info("Tushare connected successfully")
        except Exception as e:
            logger.error("Tushare init failed: %s — using mock data", e)
            self._pro = None
            self._mock = MockProvider()

        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._universe_cache: Optional[List[str]] = None

    @property
    def is_available(self) -> bool:
        return self._pro is not None

    @property
    def _use_mock(self) -> MockProvider:
        if self._mock is None:
            self._mock = MockProvider()
        return self._mock

    # ── Historical Bars ───────────────────────────────────────────

    def get_historical_bars(
        self, symbols: List[str], start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Fetch A-share daily OHLCV from Tushare pro.daily()."""
        if not self.is_available:
            logger.warning("Tushare unavailable — using mock A-share data")
            return self._use_mock.get_historical_bars(symbols, start, end)

        logger.info("Fetching A-share data for %d symbols from %s to %s",
                     len(symbols), start.date(), end.date())

        all_dfs = []
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # Process in batches to respect Tushare rate limits
        batch_size = 50  # Tushare daily() can handle comma-separated ts_codes
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            ts_codes = ",".join(batch)

            try:
                df = self._pro.daily(
                    ts_code=ts_codes,
                    start_date=start_str,
                    end_date=end_str,
                    fields="ts_code,trade_date,open,high,low,close,vol,amount",
                )

                if df is None or df.empty:
                    logger.warning("No data for batch: %s", batch)
                    continue

                # Map to universal format
                df = df.rename(columns={
                    "trade_date": "date",
                    "ts_code": "symbol",
                    "vol": "volume",
                })
                df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
                df["symbol"] = df["symbol"].apply(_ts_code_to_symbol)
                df["volume"] = df["volume"].astype(float)

                # Ensure required columns
                for col in ["open", "high", "low", "close"]:
                    if col not in df.columns:
                        df[col] = np.nan
                    else:
                        df[col] = df[col].astype(float)

                df = df[["date", "symbol", "open", "high", "low", "close", "volume"]]
                df = df.dropna(subset=["close"])
                all_dfs.append(df)

            except Exception as e:
                logger.warning("Tushare daily() failed for batch %s: %s", batch[:3], e)

            # Rate-limit courtesy
            time.sleep(0.3)

        if all_dfs:
            result = pd.concat(all_dfs, ignore_index=True)
            logger.info("Fetched A-share data: %d rows for %d symbols",
                        len(result), result["symbol"].nunique())
            return result

        # Fall back to mock
        logger.warning("No A-share data from Tushare — using mock")
        return self._use_mock.get_historical_bars(symbols, start, end)

    # ── Real-time Prices ──────────────────────────────────────────

    def get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get latest known prices for A-shares.

        Uses the most recent daily close as a proxy for "real-time" price,
        since real-time Tushare quotes require a higher subscription tier.
        """
        if not self.is_available:
            return self._use_mock.get_realtime_prices(symbols)

        prices: Dict[str, float] = {}
        today = datetime.now()

        # Try to get today's close from daily data
        try:
            ts_codes = ",".join(symbols[:100])  # Tushare limits
            today_str = today.strftime("%Y%m%d")
            df = self._pro.daily(
                ts_code=ts_codes,
                trade_date=today_str,
                fields="ts_code,close",
            )
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    prices[_ts_code_to_symbol(row["ts_code"])] = float(row["close"])
        except Exception as e:
            logger.warning("Tushare real-time price query failed: %s", e)

        # Fill missing with yesterday's close
        missing = [s for s in symbols if s not in prices]
        if missing:
            yesterday = (today - timedelta(days=1)).strftime("%Y%m%d")
            for batch_start in range(0, len(missing), 100):
                batch = missing[batch_start : batch_start + 100]
                try:
                    df = self._pro.daily(
                        ts_code=",".join(batch),
                        trade_date=yesterday,
                        fields="ts_code,close",
                    )
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            prices[_ts_code_to_symbol(row["ts_code"])] = float(row["close"])
                except Exception:
                    pass
                time.sleep(0.2)

        # Still missing → default to 10.0
        for s in symbols:
            if s not in prices:
                prices[s] = 10.0

        return prices

    # ── Quick Screen ──────────────────────────────────────────────

    def quick_screen(self, symbols: List[str], top_n: int = 200) -> List[str]:
        """Screen A-shares by multi-factor ranking.

        For large universes (>1000 symbols), uses FullMarketScreener for
        proper multi-factor selection (liquidity, momentum, quality, size).
        For smaller universes, uses simple momentum+volume ranking.
        """
        if len(symbols) <= top_n:
            return symbols

        if not self.is_available:
            return symbols[:top_n]

        # For full-market screening, use the multi-factor screener
        if len(symbols) > 500:
            try:
                from .full_market_screener import FullMarketScreener
                screener = FullMarketScreener(pro_api=self._pro)
                result = screener.screen(
                    top_n=top_n,
                    fetch_historical=True,
                    hist_lookback_days=60,
                )
                if result and len(result) >= top_n // 2:
                    logger.info("Multi-factor screener: %d -> %d candidates",
                                len(symbols), len(result))
                    return result
            except Exception as e:
                logger.warning("Multi-factor screener failed: %s — falling back to simple screen", e)

        # Simple momentum+volume ranking for smaller universes
        try:
            # Use last 20 trading days to rank by avg volume * momentum
            end = datetime.now()
            start = end - timedelta(days=60)
            df = self.get_historical_bars(symbols, start, end)
            if df.empty:
                return symbols[:top_n]

            # Group by symbol: compute avg volume + recent momentum
            scored = []
            for sym, group in df.groupby("symbol"):
                if len(group) < 5:
                    scored.append((sym, 0))
                    continue
                group = group.sort_values("date")
                avg_vol = group["volume"].tail(20).mean()
                momentum = (
                    group["close"].iloc[-1] / group["close"].iloc[-min(20, len(group))] - 1
                )
                score = abs(momentum) * np.log1p(avg_vol)
                scored.append((sym, score))

            scored.sort(key=lambda x: x[1], reverse=True)
            selected = [s for s, _ in scored[:top_n]]
            logger.info("A-share quick screen: %d -> %d candidates", len(symbols), len(selected))
            return selected

        except Exception as e:
            logger.warning("A-share quick screen failed: %s", e)
            return symbols[:top_n]

    # ── Universe ──────────────────────────────────────────────────

    def get_universe(
        self, scope: str = "liquid_cn", apply_filters: bool = True
    ) -> List[str]:
        """Get A-share stock universe from Tushare stock_basic().

        scope options:
            "csi300"    — CSI 300 constituents (~300 stocks)
            "csi500"    — CSI 500 constituents (~500 stocks)
            "all_cn"    — all listed A-shares
            "liquid_cn" — liquid stocks with price/volume filters (default)
        """
        if not self.is_available:
            logger.warning("Tushare unavailable — using mock CN universe")
            return self._use_mock.get_universe(scope, apply_filters)

        logger.info("Fetching A-share universe (scope=%s)...", scope)

        try:
            # Fetch all listed stocks
            df = self._pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,area,industry,market,list_date,list_status",
            )

            if df is None or df.empty:
                logger.warning("Tushare stock_basic returned empty")
                return []

            # Filter out delisted / suspended
            df = df[~df["list_status"].isin(CN_EXCLUDE_STATUS)]

            candidates = df["ts_code"].apply(_ts_code_to_symbol).tolist()

            # Apply scope-specific filtering
            if scope == "csi300":
                candidates = self._filter_csi300(candidates)
            elif scope == "csi500":
                candidates = self._filter_csi500(candidates)
            elif scope == "liquid_cn":
                candidates = self._filter_liquid_cn(candidates)
            # "all_cn" — no additional filtering

            logger.info("A-share universe: %d symbols (scope=%s)", len(candidates), scope)
            return sorted(candidates)

        except Exception as e:
            logger.error("Tushare stock_basic failed: %s", e)
            return []

    def _filter_csi300(self, symbols: List[str]) -> List[str]:
        """Filter to CSI 300 constituents."""
        try:
            df = self._pro.index_weight(
                index_code="000300.SH",
                trade_date=datetime.now().strftime("%Y%m%d"),
                fields="con_code",
            )
            if df is not None and not df.empty:
                constituents = set(_ts_code_to_symbol(c) for c in df["con_code"])
                return [s for s in symbols if s in constituents]
        except Exception as e:
            logger.warning("CSI 300 lookup failed: %s", e)
        # Fallback: use top 300 by market cap / alphabetical
        return sorted(symbols)[:300]

    def _filter_csi500(self, symbols: List[str]) -> List[str]:
        """Filter to CSI 500 constituents."""
        try:
            df = self._pro.index_weight(
                index_code="000905.SH",
                trade_date=datetime.now().strftime("%Y%m%d"),
                fields="con_code",
            )
            if df is not None and not df.empty:
                constituents = set(_ts_code_to_symbol(c) for c in df["con_code"])
                return [s for s in symbols if s in constituents]
        except Exception as e:
            logger.warning("CSI 500 lookup failed: %s", e)
        return sorted(symbols)[:500]

    def _filter_liquid_cn(self, symbols: List[str]) -> List[str]:
        """Filter A-shares by basic price/volume/market-cap thresholds.

        Uses Tushare daily_basic() for latest fundamental data on a sample of stocks.
        Falls back to keeping top 2000 by market cap when the API is limited.
        """
        if len(symbols) <= 2000:
            return symbols

        try:
            # Try to get daily basic data for filtering
            sample = symbols[:2000]  # API rate limit consideration
            ts_codes = ",".join(sample[:500])
            df = self._pro.daily_basic(
                ts_code=ts_codes,
                trade_date=datetime.now().strftime("%Y%m%d"),
                fields="ts_code,close,vol,total_mv",
            )
            if df is not None and not df.empty:
                passed = []
                for _, row in df.iterrows():
                    price = float(row.get("close", 0))
                    volume = float(row.get("vol", 0))
                    if CN_MIN_PRICE <= price <= CN_MAX_PRICE and volume >= CN_MIN_VOLUME:
                        passed.append(_ts_code_to_symbol(row["ts_code"]))
                return passed
        except Exception as e:
            logger.warning("daily_basic filter failed: %s", e)

        # Fallback: top 2000
        return symbols[:2000]
