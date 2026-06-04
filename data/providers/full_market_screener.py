"""
Full-Market A-Share Screener — multi-factor filtering for 全市场交易.

Uses Tushare `daily` API (universal tier) for:
  1. Latest-day liquidity screening (volume, amount, price)
  2. 60-day momentum + volatility factor computation
  3. Composite multi-factor ranking

Does NOT require daily_basic (premium tier) or index_weight (premium tier).

Pipeline:
  5000+ stocks → ST/新股 filter → ~4800 → liquidity filter → ~1500
  → multi-factor ranking → top 200-500 candidates → alpha pipeline
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("FullMarketScreener")


class FullMarketScreener:
    """
    Multi-factor A-share screener using Tushare `daily` API (universal tier).

    Screens 5000+ A-shares down to a tradeable subset via:
      1. Hard filters: ST/*ST/新股 exclusion, price, volume, amount
      2. Multi-factor composite score:
         - Momentum (20d, 60d)
         - Liquidity (avg daily amount)
         - Turnover activity
         - Low volatility preference
    """

    # ── Hard filter thresholds (tuned for small-cap coverage) ────
    MIN_LIST_DAYS = 60
    MIN_PRICE = 2.0
    MAX_PRICE = 3_000.0
    MIN_VOLUME = 100_000       # min daily volume (shares) — relaxed for small caps
    MIN_AMOUNT = 1_000_000     # min daily turnover (¥1M) — relaxed for small caps
    EXCLUDE_MARKETS = {"B股", "北交所"}

    # ── Factor weights ───────────────────────────────────────────
    FACTOR_WEIGHTS = {
        "momentum_20d": 0.25,
        "momentum_60d": 0.15,
        "liquidity": 0.20,
        "turnover": 0.10,
        "reversal_5d": 0.10,     # short-term reversal (buy dips)
        "low_volatility": 0.20,
    }

    def __init__(self, pro_api=None):
        self._pro = pro_api
        self._init_api()

    def _init_api(self):
        if self._pro is not None:
            return
        try:
            import tushare as ts
            token = os.getenv("TUSHARE_TOKEN", "")
            if token and not token.startswith("os.getenv"):
                ts.set_token(token)
                self._pro = ts.pro_api()
        except Exception as e:
            logger.warning("Tushare init failed: %s", e)

    @property
    def pro(self):
        return self._pro

    # ── Stock list ───────────────────────────────────────────────

    def get_all_listed(self) -> pd.DataFrame:
        """Fetch all listed A-shares, excluding B-shares, ST, and recent IPOs."""
        if not self.pro:
            return pd.DataFrame()
        try:
            df = self.pro.stock_basic(
                exchange="", list_status="L",
                fields="ts_code,symbol,name,area,industry,market,list_date",
            )
            if df is None or df.empty:
                return pd.DataFrame()
            logger.info("Fetched %d listed A-shares", len(df))

            if "market" in df.columns:
                df = df[~df["market"].isin(self.EXCLUDE_MARKETS)]
            if "name" in df.columns:
                df = df[~df["name"].str.contains(r"^\*?ST", na=False)]
            if "list_date" in df.columns:
                cutoff = (datetime.now() - timedelta(days=self.MIN_LIST_DAYS)).strftime("%Y%m%d")
                df = df[df["list_date"] <= cutoff]

            logger.info("After basic filters: %d stocks", len(df))
            return df.reset_index(drop=True)
        except Exception as e:
            logger.error("stock_basic failed: %s", e)
            return pd.DataFrame()

    # ── Latest-day snapshot ──────────────────────────────────────

    def _find_latest_trade_date(self) -> str:
        """Find the most recent trade date with data available."""
        for days_back in range(10):
            dt = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
            if datetime.strptime(dt, "%Y%m%d").weekday() >= 5:
                continue
            try:
                df = self.pro.daily(ts_code="000001.SZ", trade_date=dt, fields="ts_code,close")
                if df is not None and not df.empty:
                    return dt
            except Exception:
                pass
            time.sleep(0.1)
        return (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")

    def fetch_latest_snapshot(self, symbols: List[str]) -> pd.DataFrame:
        """
        Fetch latest daily snapshot for thousands of symbols in batches.

        Uses `daily` API which supports comma-separated ts_codes.
        """
        if not self.pro:
            return pd.DataFrame()

        trade_date = self._find_latest_trade_date()
        logger.info("Using trade date: %s", trade_date)

        all_dfs = []
        batch_size = 500  # Tushare supports 500+ ts_codes in a single daily() call

        total_batches = (len(symbols) + batch_size - 1) // batch_size

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            batch_num = i // batch_size + 1

            try:
                df = self.pro.daily(
                    ts_code=",".join(batch),
                    trade_date=trade_date,
                    fields="ts_code,open,high,low,close,vol,amount,pct_chg",
                )
                if df is not None and not df.empty:
                    all_dfs.append(df)
            except Exception as e:
                logger.warning("Snapshot batch %d/%d failed (%d symbols): %s",
                               batch_num, total_batches, len(batch), e)

            if batch_num % 10 == 0:
                logger.info("  Snapshot batch %d/%d (%d symbols)",
                            batch_num, total_batches, min(i + batch_size, len(symbols)))

            time.sleep(0.15)  # Rate limit (tuned for 500-ts_code batches)

        if all_dfs:
            result = pd.concat(all_dfs, ignore_index=True)
            logger.info("Snapshot: %d rows for %d symbols", len(result), result["ts_code"].nunique())
            return result
        return pd.DataFrame()

    # ── Historical data for factor computation ───────────────────

    def fetch_historical_for_factors(
        self, symbols: List[str], lookback_days: int = 60
    ) -> pd.DataFrame:
        """Fetch 60-day OHLCV for momentum/volatility factor computation."""
        if not self.pro or not symbols:
            return pd.DataFrame()

        end_date = self._find_latest_trade_date()
        start_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=lookback_days + 10)).strftime("%Y%m%d")

        all_dfs = []
        batch_size = 20  # Smaller batches for multi-day queries

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                df = self.pro.daily(
                    ts_code=",".join(batch),
                    start_date=start_date,
                    end_date=end_date,
                    fields="ts_code,trade_date,close,vol,amount,pct_chg",
                )
                if df is not None and not df.empty:
                    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
                    all_dfs.append(df)
            except Exception:
                pass
            time.sleep(0.12)  # rate limit, reduced from 0.25s

        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    # ── Hard filters ─────────────────────────────────────────────

    def apply_hard_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply binary pass/fail filters."""
        mask = pd.Series(True, index=df.index)

        if "close" in df.columns:
            c = df["close"].astype(float)
            mask &= (c >= self.MIN_PRICE) & (c <= self.MAX_PRICE)
        if "vol" in df.columns:
            mask &= df["vol"].astype(float) >= self.MIN_VOLUME
        if "amount" in df.columns:
            mask &= df["amount"].astype(float) >= self.MIN_AMOUNT

        result = df[mask].copy()
        logger.info("Hard filters: %d -> %d stocks passed", len(df), len(result))
        return result

    # ── Factor computation ───────────────────────────────────────

    def compute_factor_scores(
        self, snapshot: pd.DataFrame, hist_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Compute composite multi-factor score.

        Factors (all percentile-ranked):
          momentum_20d: 20-day return
          momentum_60d: 60-day return
          liquidity: log(avg_daily_amount)
          turnover: avg turnover rate proxy = vol / outstanding
          reversal_5d: -5-day return (buy short-term dips)
          low_volatility: inverse of 20-day realized volatility
        """
        symbols = snapshot["ts_code"].tolist()
        scores = pd.DataFrame({"ts_code": symbols})

        # ── From snapshot ──
        snap_dict = snapshot.set_index("ts_code")

        # Liquidity: log of daily turnover amount
        if "amount" in snapshot.columns:
            scores["liquidity_raw"] = np.log1p(snapshot["amount"].astype(float))
        else:
            scores["liquidity_raw"] = 0.0

        # ── From historical data ──
        mom_data = []
        if not hist_data.empty:
            for ts_code, group in hist_data.groupby("ts_code"):
                if len(group) < 10:
                    continue
                g = group.sort_values("trade_date")
                closes = g["close"].astype(float)
                amounts = g["amount"].astype(float)
                returns = closes.pct_change().dropna()

                n = len(closes)
                mom_20 = closes.iloc[-1] / closes.iloc[-min(20, n)] - 1 if n >= 5 else 0
                mom_60 = closes.iloc[-1] / closes.iloc[-min(60, n)] - 1 if n >= 15 else 0
                rev_5 = -(closes.iloc[-1] / closes.iloc[-min(5, n)] - 1) if n >= 5 else 0  # reversal
                vol = returns.std() * np.sqrt(252) if len(returns) > 5 else 1.0
                avg_amount = amounts.mean() if len(amounts) > 0 else 0

                mom_data.append({
                    "ts_code": ts_code,
                    "momentum_20d_raw": mom_20,
                    "momentum_60d_raw": mom_60,
                    "reversal_5d_raw": rev_5,
                    "volatility_raw": vol,
                    "avg_amount_60d": avg_amount,
                })

        if mom_data:
            mom_df = pd.DataFrame(mom_data)
            scores = scores.merge(mom_df, on="ts_code", how="left")
        else:
            for col in ["momentum_20d_raw", "momentum_60d_raw", "reversal_5d_raw",
                        "volatility_raw", "avg_amount_60d"]:
                scores[col] = 0.0

        # Fill NaN with neutral values
        scores = scores.fillna(0.0)

        # Use 60d avg amount for liquidity if available
        if "avg_amount_60d" in scores.columns:
            mask = scores["avg_amount_60d"] > 0
            scores.loc[mask, "liquidity_raw"] = np.log1p(scores.loc[mask, "avg_amount_60d"])

        # ── Percentile rank all factors ──
        factor_keys = [
            "momentum_20d_raw", "momentum_60d_raw", "liquidity_raw",
            "reversal_5d_raw", "volatility_raw",
        ]
        for col in factor_keys:
            if col in scores.columns:
                pct_col = col.replace("_raw", "_pct")
                scores[pct_col] = scores[col].rank(pct=True).fillna(0.5)

        # ── Composite score ──
        w = self.FACTOR_WEIGHTS
        scores["composite_score"] = (
            w["momentum_20d"] * scores.get("momentum_20d_pct", 0.5) +
            w["momentum_60d"] * scores.get("momentum_60d_pct", 0.5) +
            w["liquidity"] * scores.get("liquidity_pct", 0.5) +
            w["turnover"] * scores.get("reversal_5d_pct", 0.5) +
            w["reversal_5d"] * scores.get("reversal_5d_pct", 0.5) +
            w["low_volatility"] * (1.0 - scores.get("volatility_pct", 0.5))
        )

        return scores.sort_values("composite_score", ascending=False)

    # ── Main pipeline ────────────────────────────────────────────

    def screen(
        self,
        top_n: int = 200,
        fetch_historical: bool = True,
        hist_lookback_days: int = 60,
        max_hist_symbols: int = 1000,
    ) -> List[str]:
        """
        Run the full multi-factor screening pipeline.

        Args:
            top_n: Return top N candidates
            fetch_historical: Compute momentum/volatility factors
            hist_lookback_days: Days of history for factors
            max_hist_symbols: Max symbols to fetch history for (performance)

        Returns:
            Ranked ts_code list
        """
        logger.info("=" * 55)
        logger.info("  Full-Market A-Share Multi-Factor Screener")
        logger.info("=" * 55)
        start_time = time.time()

        # 1. Get all listed stocks
        all_stocks = self.get_all_listed()
        if all_stocks.empty:
            return self._fallback_symbols(top_n)
        symbols = all_stocks["ts_code"].tolist()
        logger.info("Step 1: %d listed stocks (excl. B/ST/新股)", len(symbols))

        # 2. Fetch latest snapshot
        snapshot = self.fetch_latest_snapshot(symbols)
        if snapshot.empty:
            logger.warning("No snapshot data — returning all symbols")
            return symbols[:top_n]
        logger.info("Step 2: Snapshot data for %d symbols", len(snapshot))

        # 3. Apply hard filters
        passed = self.apply_hard_filters(snapshot)
        logger.info("Step 3: %d stocks passed hard filters (price/vol/amount)", len(passed))

        if len(passed) < top_n:
            logger.warning("Only %d stocks passed filters — relaxing", len(passed))
            # Take all passed + top by amount from rest
            if "amount" in snapshot.columns:
                remaining = snapshot[~snapshot["ts_code"].isin(passed["ts_code"])]
                extra = remaining.nlargest(top_n - len(passed), "amount")
                passed = pd.concat([passed, extra])

        # 4. Fetch historical data for factors (limit to top candidates by liquidity)
        passed_syms = passed["ts_code"].tolist()
        hist_symbols = passed_syms[:max_hist_symbols]

        hist_data = pd.DataFrame()
        if fetch_historical and hist_symbols:
            hist_data = self.fetch_historical_for_factors(hist_symbols, hist_lookback_days)
            if not hist_data.empty:
                logger.info("Step 4: Historical data for %d symbols (%d rows)",
                            hist_data["ts_code"].nunique(), len(hist_data))
            else:
                logger.warning("Step 4: No historical data — using snapshot-only scoring")

        # 5. Compute composite scores
        scored = self.compute_factor_scores(passed, hist_data)
        logger.info("Step 5: Composite scores computed")

        # 6. Top N
        top = scored.head(top_n)["ts_code"].tolist()

        elapsed = time.time() - start_time
        logger.info("=" * 55)
        logger.info("  ✅ %d candidates in %.1fs", len(top), elapsed)
        logger.info("  Top 10: %s", ", ".join(top[:10]))
        logger.info("=" * 55)

        return top

    def _fallback_symbols(self, top_n: int) -> List[str]:
        """Fallback symbol list (沪深300 + 中证500 core constituents)."""
        fallback = [
            "600519.SH", "601318.SH", "600036.SH", "000858.SZ", "002415.SZ",
            "600276.SH", "601166.SH", "000333.SZ", "600900.SH", "601398.SH",
            "000001.SZ", "002594.SZ", "300750.SZ", "601899.SH", "600030.SH",
            "000651.SZ", "002142.SZ", "300059.SZ", "600585.SH", "601288.SH",
            "000725.SZ", "002475.SZ", "300760.SZ", "600809.SH", "601857.SH",
            "000568.SZ", "002304.SZ", "300498.SZ", "600031.SH", "601088.SH",
            "000063.SZ", "002714.SZ", "300274.SZ", "600309.SH", "601012.SH",
            "000002.SZ", "002027.SZ", "300124.SZ", "600887.SH", "601668.SH",
            "000100.SZ", "002050.SZ", "300015.SZ", "600048.SH", "601888.SH",
            "000625.SZ", "002230.SZ", "300122.SZ", "600690.SH", "603259.SH",
        ]
        logger.warning("Using fallback symbol list (%d stocks)", len(fallback))
        return fallback[:top_n]
