"""
Akshare DataProvider — free A-share market data via akshare (东方财富 API).

Implements the DataProvider interface using akshare's stock_zh_a_hist()
for historical daily OHLCV and stock_zh_a_spot_em() for real-time prices.

No token, no积分 — completely free and unlimited.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .base import DataProvider
from .mock_provider import MockProvider

logger = logging.getLogger("AkshareProvider")

# ── A-share filtering defaults ─────────────────────────────────────
CN_MIN_PRICE = 2.0          # minimum share price (CNY)
CN_MIN_VOLUME = 100_000     # minimum volume (shares)
CN_MAX_PRICE = 3_000.0      # skip ultra-expensive stocks
CN_MIN_AMOUNT = 1_000_000    # minimum daily amount (¥1M)


def _patch_akshare_network():
    """Ensure akshare uses direct connection (no proxy). Called once on import."""
    try:
        import requests
        import akshare
        # Override akshare's internal request function to use direct connection
        if hasattr(akshare, '_requests_get'):
            return  # already patched

        akshare._requests_get = requests.get
        def _direct_get(url, **kwargs):
            kwargs.setdefault('timeout', 15)
            s = requests.Session()
            s.trust_env = False  # bypass system proxy
            return s.get(url, **kwargs)
        requests.get = _direct_get
        akshare._requests_get = _direct_get
    except Exception:
        pass  # best-effort


_patch_akshare_network()


def _normalize_symbol(symbol: str) -> str:
    """Normalize akshare symbol (000001) to standard format (000001.SZ)."""
    symbol = symbol.strip().upper()
    if '.' in symbol:
        return symbol
    # Determine exchange by code prefix
    code = symbol.zfill(6)
    if code.startswith(('688', '689')):
        return f"{code}.SH"
    elif code.startswith(('6', '9')):
        return f"{code}.SH"
    elif code.startswith(('8', '4')):
        return f"{code}.BJ"
    else:
        return f"{code}.SZ"


def _strip_exchange(symbol: str) -> str:
    """Strip exchange suffix: '000001.SZ' -> '000001'."""
    return symbol.split('.')[0]


class AkshareProvider(DataProvider):
    """A-share market data via akshare (东方财富), with mock fallback."""

    def __init__(self):
        self._available = False
        self._mock = MockProvider()
        self._universe_cache: Optional[List[str]] = None

        try:
            import akshare as ak
            self._ak = ak
            # Quick connectivity test
            test = ak.stock_zh_a_spot_em()
            if test is not None and not test.empty:
                self._available = True
                logger.info("Akshare connected — %d stocks in spot list", len(test))
            else:
                logger.warning("Akshare returned empty spot data")
        except ImportError:
            logger.warning("akshare not installed — using mock A-share data. pip install akshare")
        except Exception as e:
            logger.warning("Akshare init failed: %s — using mock data", e)

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def _use_mock(self) -> MockProvider:
        if self._mock is None:
            self._mock = MockProvider()
        return self._mock

    # ── Historical Bars ───────────────────────────────────────────

    def get_historical_bars(
        self, symbols: List[str], start: datetime, end: datetime
    ) -> pd.DataFrame:
        """Fetch A-share daily OHLCV from akshare stock_zh_a_hist()."""
        if not self.is_available:
            logger.warning("Akshare unavailable — using mock A-share data")
            return self._use_mock.get_historical_bars(symbols, start, end)

        logger.info("Fetching A-share data for %d symbols from %s to %s",
                     len(symbols), start.date(), end.date())

        all_dfs = []
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        for i, symbol in enumerate(symbols):
            code = _strip_exchange(symbol)
            try:
                df = self._ak.stock_zh_a_hist(
                    symbol=code,
                    period='daily',
                    start_date=start_str,
                    end_date=end_str,
                    adjust='qfq',  # 前复权
                )

                if df is None or df.empty:
                    continue

                # Map akshare columns to universal format
                # akshare columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
                col_map = {
                    '日期': 'date', '开盘': 'open', '收盘': 'close',
                    '最高': 'high', '最低': 'low', '成交量': 'volume',
                }
                df = df.rename(columns=col_map)
                df['date'] = pd.to_datetime(df['date'])
                df['symbol'] = _normalize_symbol(code)

                for col in ['open', 'high', 'low', 'close']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                if 'volume' in df.columns:
                    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

                df = df[['date', 'symbol', 'open', 'high', 'low', 'close', 'volume']]
                df = df.dropna(subset=['close'])
                if not df.empty:
                    all_dfs.append(df)

            except Exception as e:
                logger.debug("Akshare fetch failed for %s: %s", symbol, e)

            # Rate-limit courtesy: 0.1s between requests
            if (i + 1) % 50 == 0:
                logger.info("  ... %d/%d symbols fetched", i + 1, len(symbols))
                time.sleep(0.5)
            else:
                time.sleep(0.05)

        if all_dfs:
            result = pd.concat(all_dfs, ignore_index=True)
            logger.info("Fetched A-share data: %d rows for %d symbols",
                        len(result), result['symbol'].nunique())
            return result

        logger.warning("No A-share data from akshare — using mock")
        return self._use_mock.get_historical_bars(symbols, start, end)

    # ── Real-time Prices ──────────────────────────────────────────

    def get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get latest prices from akshare spot market data."""
        if not self.is_available:
            return self._use_mock.get_realtime_prices(symbols)

        prices: Dict[str, float] = {}
        try:
            spot = self._ak.stock_zh_a_spot_em()
            if spot is not None and not spot.empty:
                # Columns: 代码, 名称, 最新价, ...
                spot['code'] = spot['代码'].apply(_normalize_symbol)
                spot_dict = dict(zip(spot['code'], spot['最新价']))
                for sym in symbols:
                    if sym in spot_dict:
                        p = spot_dict[sym]
                        prices[sym] = float(p) if pd.notna(p) else 0.0
        except Exception as e:
            logger.warning("Akshare spot fetch failed: %s", e)

        # Fill missing with latest close from historical
        missing = [s for s in symbols if s not in prices or prices.get(s, 0) <= 0]
        if missing:
            end = datetime.now()
            start = end - timedelta(days=10)
            try:
                hist = self.get_historical_bars(missing, start, end)
                if not hist.empty:
                    latest = hist.sort_values('date').groupby('symbol').last()
                    for sym in missing:
                        if sym in latest.index:
                            prices[sym] = float(latest.loc[sym, 'close'])
            except Exception:
                pass

        # Still missing → default 10.0
        for s in symbols:
            if s not in prices or prices.get(s, 0) <= 0:
                prices[s] = 10.0

        return prices

    # ── Quick Screen ──────────────────────────────────────────────

    def quick_screen(self, symbols: List[str], top_n: int = 200) -> List[str]:
        """Screen A-shares by momentum + volume ranking."""
        if len(symbols) <= top_n:
            return symbols

        if not self.is_available:
            return symbols[:top_n]

        # Use spot data for quick filtering
        try:
            spot = self._ak.stock_zh_a_spot_em()
            if spot is not None and not spot.empty:
                spot['symbol'] = spot['代码'].apply(_normalize_symbol)
                spot = spot[spot['symbol'].isin(symbols)]

                # Filter basic criteria
                spot['price'] = pd.to_numeric(spot['最新价'], errors='coerce')
                spot['volume'] = pd.to_numeric(spot['成交量'], errors='coerce')
                spot['amount'] = pd.to_numeric(spot['成交额'], errors='coerce')
                spot['pct_chg'] = pd.to_numeric(spot['涨跌幅'], errors='coerce')

                valid = spot[
                    (spot['price'] >= CN_MIN_PRICE) &
                    (spot['price'] <= CN_MAX_PRICE) &
                    (spot['volume'] >= CN_MIN_VOLUME) &
                    (spot['amount'] >= CN_MIN_AMOUNT)
                ].copy()

                if valid.empty:
                    return symbols[:top_n]

                # Score: abs(momentum) * log(amount)
                valid['score'] = valid['pct_chg'].abs() * np.log1p(valid['amount'])
                valid = valid.sort_values('score', ascending=False)

                selected = valid['symbol'].head(top_n).tolist()
                logger.info("A-share quick screen: %d -> %d candidates", len(symbols), len(selected))
                return selected

        except Exception as e:
            logger.warning("Akshare quick screen failed: %s", e)

        return symbols[:top_n]

    # ── Universe ──────────────────────────────────────────────────

    def get_universe(
        self, scope: str = "liquid_cn", apply_filters: bool = True
    ) -> List[str]:
        """Get A-share stock universe from akshare spot data.

        scope options:
            "csi300"    — CSI 300 constituents (~300 stocks)
            "csi500"    — CSI 500 constituents (~500 stocks)
            "all_cn"    — all listed A-shares (~5000 stocks)
            "liquid_cn" — liquid stocks with price/volume filters (default)
        """
        if not self.is_available:
            logger.warning("Akshare unavailable — using mock CN universe")
            return self._use_mock.get_universe(scope, apply_filters)

        logger.info("Fetching A-share universe (scope=%s)...", scope)

        try:
            # Fetch all A-share stocks
            spot = self._ak.stock_zh_a_spot_em()
            if spot is None or spot.empty:
                return []

            spot['symbol'] = spot['代码'].apply(_normalize_symbol)
            spot['price'] = pd.to_numeric(spot['最新价'], errors='coerce')
            spot['volume'] = pd.to_numeric(spot['成交量'], errors='coerce')
            spot['amount'] = pd.to_numeric(spot['成交额'], errors='coerce')
            spot['total_mv'] = pd.to_numeric(spot['总市值'], errors='coerce')

            # Basic filters for all scopes
            spot = spot[spot['price'] > 0]

            if scope == "csi300":
                candidates = self._filter_index_constituents(spot, "000300")
            elif scope == "csi500":
                candidates = self._filter_index_constituents(spot, "000905")
            elif scope == "liquid_cn":
                candidates = self._filter_liquid(spot)
            elif scope == "all_cn":
                candidates = spot['symbol'].tolist()
            else:
                candidates = spot['symbol'].tolist()

            if apply_filters and scope not in ("csi300", "csi500"):
                candidates = self._apply_basic_filters(spot, candidates)

            logger.info("A-share universe: %d symbols (scope=%s)", len(candidates), scope)
            return sorted(candidates)

        except Exception as e:
            logger.error("Akshare universe fetch failed: %s", e)
            return []

    def _filter_index_constituents(self, spot: pd.DataFrame, index_code: str) -> List[str]:
        """Filter to index constituents using akshare."""
        try:
            if index_code == "000300":
                df = self._ak.index_stock_cons_csindex(symbol="000300")
            elif index_code == "000905":
                df = self._ak.index_stock_cons_csindex(symbol="000905")
            else:
                return spot['symbol'].tolist()

            if df is not None and not df.empty:
                # Column: 成分券代码
                code_col = [c for c in df.columns if '代码' in c or 'code' in c.lower()]
                if code_col:
                    constituents = set(_normalize_symbol(c) for c in df[code_col[0]])
                    result = spot[spot['symbol'].isin(constituents)]['symbol'].tolist()
                    logger.info("%s constituents: %d", index_code, len(result))
                    return result
        except Exception as e:
            logger.warning("Index constituent fetch failed for %s: %s", index_code, e)

        # Fallback: top by market cap
        spot = spot.sort_values('total_mv', ascending=False)
        n = 300 if index_code == "000300" else 500
        return spot.head(n)['symbol'].tolist()

    def _filter_liquid(self, spot: pd.DataFrame) -> List[str]:
        """Filter to liquid stocks."""
        valid = spot[
            (spot['price'] >= CN_MIN_PRICE) &
            (spot['price'] <= CN_MAX_PRICE) &
            (spot['volume'] >= CN_MIN_VOLUME) &
            (spot['amount'] >= CN_MIN_AMOUNT)
        ]
        return valid['symbol'].tolist()

    def _apply_basic_filters(self, spot: pd.DataFrame, candidates: List[str]) -> List[str]:
        """Apply ST/*ST/新股 filters."""
        try:
            # Filter out ST, *ST, N (新股首日), 退市
            st_pattern = spot['名称'].str.contains(r'ST|\*ST|N\w|退', na=False)
            excluded_names = set(spot[st_pattern]['symbol'])
            candidates = [c for c in candidates if c not in excluded_names]
        except Exception:
            pass
        return candidates


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  AkshareProvider Smoke Test")
    print("=" * 60)

    provider = AkshareProvider()
    print(f"Available: {provider.is_available}")

    if provider.is_available:
        # Test universe
        universe = provider.get_universe("liquid_cn")
        print(f"Universe (liquid_cn): {len(universe)} stocks")
        if universe:
            print(f"  Sample: {', '.join(universe[:5])}")

        # Test historical bars
        test_symbols = universe[:3] if len(universe) >= 3 else universe
        if test_symbols:
            end = datetime.now()
            start = end - timedelta(days=60)
            print(f"\nFetching {test_symbols} from {start.date()} to {end.date()}...")
            df = provider.get_historical_bars(test_symbols, start, end)
            print(f"  Rows: {len(df)}")
            if not df.empty:
                print(f"  Date range: {df['date'].min()} -> {df['date'].max()}")
                print(df.head(3))

        # Test real-time
        prices = provider.get_realtime_prices(test_symbols)
        print(f"\nReal-time prices: { {s: round(p, 2) for s, p in list(prices.items())[:5]} }")
    else:
        print("Akshare not available — using mock fallback.")
