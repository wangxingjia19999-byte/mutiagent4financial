"""
Abstract DataProvider — defines the interface for market data retrieval.

All concrete providers MUST return the universal DataFrame format:
    [date, symbol, open, high, low, close, volume]
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List

import pandas as pd


class DataProvider(ABC):
    """Abstract data provider for market data.

    All downstream agents (Alpha, Risk, Portfolio, Backtest) consume
    data in the universal format: a long-form DataFrame with columns
    [date, symbol, open, high, low, close, volume].
    """

    @abstractmethod
    def get_historical_bars(
        self, symbols: List[str], start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars.

        Returns:
            DataFrame with columns: date (datetime), symbol (str),
            open, high, low, close, volume (all float).
            Multi-symbol results are concatenated vertically.
        """
        ...

    @abstractmethod
    def get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch current/latest prices.

        Returns:
            {symbol: price} dict. Falls back to latest close if
            real-time data is unavailable.
        """
        ...

    @abstractmethod
    def get_universe(
        self, scope: str = "liquid", apply_filters: bool = True
    ) -> List[str]:
        """Get a list of tradeable symbols.

        Args:
            scope: market-specific scope string (e.g. "sp500", "csi300")
            apply_filters: if True, apply price/volume/liquidity filters

        Returns:
            List of symbol strings.
        """
        ...
