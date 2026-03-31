from __future__ import annotations

import os
from dataclasses import dataclass

import pandas as pd
import tushare as ts


@dataclass
class TushareClient:
    token: str | None = None

    def __post_init__(self) -> None:
        resolved_token = (self.token or os.getenv("TUSHARE_TOKEN", "")).strip()
        if not resolved_token:
            raise ValueError("缺少 Tushare Token，请设置 TUSHARE_TOKEN 或传入 token")

        self.token = resolved_token
        self.pro = ts.pro_api(self.token)

    def get_stock_basic(
        self,
        exchange: str = "",
        list_status: str = "L",
        fields: str = "ts_code,symbol,name,area,industry,market,list_date",
    ) -> pd.DataFrame:
        return self.pro.stock_basic(exchange=exchange, list_status=list_status, fields=fields)

    def get_daily(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 30,
    ) -> pd.DataFrame:
        daily = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily.empty:
            return daily

        daily = daily.sort_values("trade_date", ascending=False)
        return daily.head(limit)

    def get_daily_basic(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 30,
    ) -> pd.DataFrame:
        daily_basic = self.pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if daily_basic.empty:
            return daily_basic

        daily_basic = daily_basic.sort_values("trade_date", ascending=False)
        return daily_basic.head(limit)

    def get_merged_daily_data(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 120,
    ) -> pd.DataFrame:
        daily = self.get_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, limit=limit)
        if daily.empty:
            return daily

        daily_basic = self.get_daily_basic(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if daily_basic.empty:
            return daily

        merged = pd.merge(daily, daily_basic, on=["ts_code", "trade_date"], how="left")
        merged = merged.sort_values("trade_date", ascending=False)
        return merged

    def build_market_snapshot(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 30,
    ) -> str:
        df = self.get_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, limit=limit)
        if df.empty:
            return f"{ts_code} 在指定区间没有拉取到日线数据。"

        latest = df.iloc[0]
        closes = df["close"].astype(float)
        ma5 = closes.head(5).mean() if len(closes) >= 5 else closes.mean()
        ma10 = closes.head(10).mean() if len(closes) >= 10 else closes.mean()
        pct_mean = df["pct_chg"].astype(float).head(10).mean()
        vol_mean = df["vol"].astype(float).head(10).mean()

        return (
            f"{ts_code} 最新交易日: {latest['trade_date']}\\n"
            f"收盘价: {latest['close']}，涨跌幅: {latest['pct_chg']}%\\n"
            f"近5日均线: {ma5:.2f}，近10日均线: {ma10:.2f}\\n"
            f"近10日平均涨跌幅: {pct_mean:.2f}%\\n"
            f"近10日平均成交量(手): {vol_mean:.0f}"
        )
