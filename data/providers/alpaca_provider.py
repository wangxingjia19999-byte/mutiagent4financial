"""
Alpaca DataProvider — implements DataProvider for US stocks via Alpaca Markets API.

Extracted from orchestrator.py fetch_data() / fetch_realtime_prices() and
market_universe.py get_market_universe().
"""

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .base import DataProvider

logger = logging.getLogger("AlpacaProvider")

_project_root = Path(__file__).resolve().parents[2]
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


class AlpacaProvider(DataProvider):
    """US stock market data via Alpaca, with yfinance fallback."""

    # ── Universe defaults ──────────────────────────────────────────
    MIN_PRICE = 2.0
    MIN_VOLUME = 100_000
    MAX_PRICE = 5_000.0
    EXCLUDE_EXCHANGES = {"OTC", "OTCBB", "PINK"}

    def __init__(self, api_key: str = None, secret_key: str = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")

        # Lazy init
        self._data_client = None
        self._trading_client = None

    @property
    def data_client(self):
        if self._data_client is None and self.api_key:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                self._data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
            except Exception as e:
                logger.warning("Alpaca data client unavailable: %s", e)
        return self._data_client

    @property
    def trading_client(self):
        if self._trading_client is None and self.api_key:
            try:
                from alpaca.trading.client import TradingClient
                self._trading_client = TradingClient(self.api_key, self.secret_key)
            except Exception as e:
                logger.warning("Alpaca trading client unavailable: %s", e)
        return self._trading_client

    # ── Historical Bars ───────────────────────────────────────────

    def get_historical_bars(
        self, symbols: List[str], start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Fetch daily OHLCV from Alpaca, falling back to yfinance, then mock."""
        logger.info("Fetching data for %s from %s to %s", symbols, start.date(), end.date())

        # 1. Try Alpaca
        if self.data_client:
            try:
                from alpaca.data.requests import StockBarsRequest
                from alpaca.data.timeframe import TimeFrame

                request_params = StockBarsRequest(
                    symbol_or_symbols=symbols,
                    timeframe=TimeFrame.Day,
                    start=start,
                    end=end,
                )
                bars = self.data_client.get_stock_bars(request_params)
                df = bars.df.reset_index()
                df = df.rename(columns={"timestamp": "date"})
                df["date"] = df["date"].dt.tz_localize(None)
                return df
            except Exception as e:
                logger.error("Alpaca data fetch failed: %s. Using fallback.", e)

        # 2. Try yfinance
        try:
            import logging as log_mod
            log_mod.getLogger("yfinance").setLevel(log_mod.CRITICAL)
            import yfinance as yf

            all_dfs = []
            for symbol in symbols:
                try:
                    df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
                    if df.empty:
                        continue
                    if isinstance(df.columns, pd.MultiIndex):
                        if df.columns.nlevels > 1:
                            df.columns = df.columns.droplevel(1)
                    df = df.reset_index()
                    df.columns = [str(c).lower() for c in df.columns]
                    if "date" not in df.columns:
                        date_cols = [c for c in df.columns if "date" in c]
                        if date_cols:
                            df = df.rename(columns={date_cols[0]: "date"})
                    required_cols = ["open", "high", "low", "close", "volume"]
                    valid_cols = [c for c in required_cols if c in df.columns]
                    if "date" in df.columns:
                        df = df[["date"] + valid_cols].copy()
                        df["symbol"] = symbol
                        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
                        all_dfs.append(df)
                except Exception as e:
                    logger.warning("Failed to process %s: %s", symbol, e)
                    continue

            if all_dfs:
                logger.info("Fetched real data via yfinance for %d symbols", len(all_dfs))
                return pd.concat(all_dfs, ignore_index=True)
        except ImportError:
            logger.warning("yfinance not installed. Falling back to mock data.")
        except Exception as e:
            logger.error("yfinance fetch failed: %s", e)

        # 3. Mock data
        return self._generate_mock_data(symbols, start, end)

    def _generate_mock_data(
        self, symbols: List[str], start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Generate synthetic regime-switching price paths."""
        all_dfs = []
        dates = pd.date_range(start=start, end=end, freq="B")
        n = len(dates)

        for symbol in symbols:
            seed_val = (hash(symbol) + int(start.timestamp())) % (2 ** 32)
            np.random.seed(seed_val)

            p1 = n // 3
            p2 = n // 3
            p3 = n - p1 - p2

            r1 = np.random.normal(0.001, 0.01, p1)
            r2 = np.random.normal(-0.0015, 0.02, p2)
            r3 = np.random.normal(0.0005, 0.015, p3)
            rets = np.concatenate([r1, r2, r3])
            price = 100.0 * np.cumprod(1 + rets)

            df = pd.DataFrame({
                "date": dates,
                "symbol": symbol,
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "volume": np.random.randint(1000, 10000, n),
            })
            all_dfs.append(df)

        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

    # ── Real-time Prices ──────────────────────────────────────────

    def get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch real-time prices from Alpaca snapshots."""
        prices: Dict[str, float] = {}

        if self.data_client:
            try:
                from alpaca.data.requests import StockSnapshotRequest

                for i in range(0, len(symbols), 500):
                    batch = symbols[i : i + 500]
                    req = StockSnapshotRequest(symbol_or_symbols=batch)
                    snaps = self.data_client.get_stock_snapshot(req)
                    for sym, snap in (snaps or {}).items():
                        trade = getattr(snap, "latest_trade", None)
                        bar = getattr(snap, "daily_bar", None)
                        p = 0.0
                        if trade and getattr(trade, "price", 0):
                            p = float(trade.price)
                        elif bar and getattr(bar, "close", 0):
                            p = float(bar.close)
                        if p > 0:
                            prices[sym] = p

                if prices:
                    logger.info("Real-time prices from Alpaca: %d symbols", len(prices))
                    return prices
            except Exception as e:
                logger.warning("Alpaca snapshot prices failed: %s", e)

        # Mock fallback
        logger.warning("Using mock real-time prices ($100 each)")
        return {s: 100.0 for s in symbols}

    # ── Quick Pre-Screen (momentum + volume) ──────────────────────

    def quick_screen(self, symbols: List[str], top_n: int = 200) -> List[str]:
        """Narrow down a large universe via momentum + volume snapshots."""
        if len(symbols) <= top_n:
            return symbols

        if not self.data_client:
            logger.info("No Alpaca data client — using first %d symbols", top_n)
            return symbols[:top_n]

        try:
            from alpaca.data.requests import StockSnapshotRequest

            scored: List[tuple] = []
            batch_size = 500

            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]
                try:
                    req = StockSnapshotRequest(symbol_or_symbols=batch)
                    snaps = self.data_client.get_stock_snapshot(req)

                    for sym, snap in (snaps or {}).items():
                        bar = getattr(snap, "daily_bar", None)
                        prev_bar = getattr(snap, "previous_daily_bar", None)
                        trade = getattr(snap, "latest_trade", None)

                        price = 0.0
                        if trade and getattr(trade, "price", 0):
                            price = float(trade.price)
                        elif bar and getattr(bar, "close", 0):
                            price = float(bar.close)

                        volume = float(getattr(bar, "volume", 0)) if bar else 0.0

                        if price < 2 or volume < 50_000:
                            continue

                        prev_close = (
                            float(getattr(prev_bar, "close", price))
                            if prev_bar
                            else price
                        )
                        change_pct = (
                            (price - prev_close) / prev_close if prev_close > 0 else 0
                        )
                        score = abs(change_pct) * np.log1p(volume)
                        scored.append((sym, score))

                except Exception as e:
                    logger.warning("Snapshot screen batch failed: %s", e)
                    scored.extend((s, 0) for s in batch[:50])

            scored.sort(key=lambda x: x[1], reverse=True)
            selected = [s for s, _ in scored[:top_n]]
            logger.info("Quick screen: %d -> %d candidates", len(symbols), len(selected))
            return selected

        except Exception as e:
            logger.warning("Quick screen failed: %s — falling back", e)
            return symbols[:top_n]

    # ── Universe ──────────────────────────────────────────────────

    @staticmethod
    def _is_desired_exchange(exchange: str) -> bool:
        if not exchange:
            return False
        return exchange.upper() not in AlpacaProvider.EXCLUDE_EXCHANGES

    def get_universe(
        self, scope: str = "liquid", apply_filters: bool = True
    ) -> List[str]:
        """Get US stock universe from Alpaca."""
        assets = self._fetch_alpaca_assets()
        if not assets:
            logger.warning("No assets from Alpaca — returning empty list")
            return []

        candidates = [
            a["symbol"]
            for a in assets
            if a["tradable"]
            and self._is_desired_exchange(a.get("exchange", ""))
        ]

        logger.info(
            "Alpaca universe: %d tradable on major exchanges (from %d total)",
            len(candidates),
            len(assets),
        )

        if apply_filters:
            candidates = self._filter_by_volume_and_price(candidates)

        candidates = sorted(candidates)

        scope_caps = {"nasdaq100": 100, "sp500": 500, "liquid": 2000, "all": len(candidates)}
        cap = scope_caps.get(scope, 2000)
        return candidates[:cap]

    def _fetch_alpaca_assets(self) -> List[dict]:
        """Fetch ALL tradeable US equity assets from Alpaca."""
        if not self.trading_client:
            return []

        try:
            from alpaca.trading.requests import GetAssetsRequest
            from alpaca.trading.enums import AssetClass, AssetStatus

            req = GetAssetsRequest(
                asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE
            )
            assets = self.trading_client.get_all_assets(req)

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
        except Exception as e:
            logger.warning("Alpaca asset fetch failed: %s", e)
            return []

    def _filter_by_volume_and_price(self, symbols: List[str]) -> List[str]:
        """Filter by price and volume using Alpaca snapshots."""
        if not symbols or not self.data_client:
            return symbols

        try:
            from alpaca.data.requests import StockSnapshotRequest

            passed: List[str] = []
            batch_size = 500

            for i in range(0, len(symbols), batch_size):
                batch = symbols[i : i + batch_size]
                try:
                    req = StockSnapshotRequest(symbol_or_symbols=batch)
                    snapshots = self.data_client.get_stock_snapshot(req)

                    for sym, snap in (snapshots or {}).items():
                        trade = getattr(snap, "latest_trade", None)
                        bar = getattr(snap, "daily_bar", None)

                        p = 0.0
                        if trade and getattr(trade, "price", 0):
                            p = float(trade.price)
                        elif bar and getattr(bar, "close", 0):
                            p = float(bar.close)

                        v = float(getattr(bar, "volume", 0)) if bar else 0.0

                        if p <= 0 or v <= 0:
                            passed.append(sym)
                        elif self.MIN_PRICE <= p <= self.MAX_PRICE and v >= self.MIN_VOLUME:
                            passed.append(sym)

                except Exception as e:
                    logger.warning(
                        "Snapshot batch %d–%d failed: %s — keeping all", i, i + len(batch), e
                    )
                    passed.extend(batch)

                time.sleep(0.15)

            logger.info("Price/volume filter: %d -> %d symbols passed", len(symbols), len(passed))
            return passed
        except Exception as e:
            logger.warning("Price/volume filter failed: %s", e)
            return symbols
