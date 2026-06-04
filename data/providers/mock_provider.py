"""
Mock DataProvider — generates synthetic OHLCV data for testing.

Mirrors the mock fallback logic from orchestrator.py fetch_data().
"""

import hashlib
from datetime import datetime
from typing import Dict, List

import numpy as np
import pandas as pd

from .base import DataProvider


def _stable_hash(symbol: str) -> int:
    """Stable hash for deterministic mock data."""
    return int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)


class MockProvider(DataProvider):
    """Generates regime-switching synthetic price paths for testing."""

    def __init__(self, seed_base: int = 42):
        self._seed_base = seed_base

    def get_historical_bars(
        self, symbols: List[str], start: datetime, end: datetime
    ) -> pd.DataFrame:
        all_dfs = []
        dates = pd.date_range(start=start, end=end, freq="B")
        n = len(dates)

        for symbol in symbols:
            seed_val = (_stable_hash(symbol) + self._seed_base + int(start.timestamp())) % (2 ** 32)
            np.random.seed(seed_val)

            # Construct three regimes: bullish, bearish, rebound
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

    def get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        return {s: 100.0 for s in symbols}

    def get_universe(
        self, scope: str = "liquid", apply_filters: bool = True
    ) -> List[str]:
        # Return some plausible mock symbols based on scope
        prefix = "MOCK"
        sizes = {"nasdaq100": 100, "sp500": 500, "liquid": 200, "csi300": 300,
                 "csi500": 500, "all": 1000, "all_cn": 1000, "liquid_cn": 200}
        n = sizes.get(scope, 100)
        return [f"{prefix}{i:04d}" for i in range(n)]
