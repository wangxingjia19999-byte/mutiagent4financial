from __future__ import annotations

import os
from datetime import datetime, timedelta
from dataclasses import dataclass
import re
from typing import Any

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

    def _safe_call(self, api_name: str, **kwargs: Any) -> pd.DataFrame:
        api = getattr(self.pro, api_name, None)
        if not callable(api):
            return pd.DataFrame()
        try:
            result = api(**kwargs)
            return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _normalize_news_datetime(value: str | None, is_end: bool = False) -> str:
        if value and value.strip():
            raw = value.strip()
            if re.fullmatch(r"\d{8}", raw):
                suffix = "23:59:59" if is_end else "00:00:00"
                return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]} {suffix}"
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}$", raw):
                suffix = "23:59:59" if is_end else "00:00:00"
                return f"{raw} {suffix}"
            return raw

        default_time = datetime.now() if is_end else datetime.now() - timedelta(days=30)
        return default_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_stock_name(self, ts_code: str) -> str:
        df = self._safe_call(
            "stock_basic",
            exchange="",
            list_status="L",
            fields="ts_code,name",
        )
        if df.empty:
            return ""

        matched = df.loc[df["ts_code"] == ts_code, "name"]
        if matched.empty:
            return ""
        return str(matched.iloc[0])

    @staticmethod
    def _pick_col(row: pd.Series, candidates: list[str], default: str = "") -> str:
        for col in candidates:
            if col in row and pd.notna(row[col]):
                return str(row[col])
        return default

    def get_stock_news(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        symbol = ts_code.split(".")[0]
        stock_name = self.get_stock_name(ts_code)
        keywords = [kw for kw in [ts_code, symbol, stock_name] if kw]

        normalized_start = self._normalize_news_datetime(start_date, is_end=False)
        normalized_end = self._normalize_news_datetime(end_date, is_end=True)

        frames: list[pd.DataFrame] = []

        news_df = self._safe_call(
            "news",
            start_date=normalized_start,
            end_date=normalized_end,
            fields="datetime,content,title,channels",
        )
        if not news_df.empty:
            frames.append(news_df)

        for src in ["新浪财经", "同花顺", "东方财富", "华尔街见闻"]:
            major_df = self._safe_call(
                "major_news",
                src=src,
                start_date=normalized_start,
                end_date=normalized_end,
            )
            if not major_df.empty:
                frames.append(major_df)

        if not frames:
            return pd.DataFrame(columns=["title", "pub_time", "source", "content"])

        merged = pd.concat(frames, ignore_index=True)
        normalized_rows: list[dict[str, str]] = []
        for _, row in merged.iterrows():
            title = self._pick_col(row, ["title", "name", "content"], default="")
            pub_time = self._pick_col(row, ["pub_time", "datetime", "date", "create_time"], default="")
            source = self._pick_col(row, ["src", "media", "channels"], default="")
            content = self._pick_col(row, ["content", "summary"], default="")

            text = f"{title} {content}"
            if keywords and not any(kw in text for kw in keywords):
                continue

            normalized_rows.append(
                {
                    "title": title.strip(),
                    "pub_time": pub_time.strip(),
                    "source": source.strip(),
                    "content": content.strip(),
                }
            )

        if not normalized_rows:
            return pd.DataFrame(columns=["title", "pub_time", "source", "content"])

        result = pd.DataFrame(normalized_rows).drop_duplicates(subset=["title", "pub_time"], keep="first")
        if "pub_time" in result.columns:
            result = result.sort_values("pub_time", ascending=False)
        return result.head(limit)

    def get_financial_indicators(self, ts_code: str, limit: int = 8) -> pd.DataFrame:
        df = self._safe_call("fina_indicator", ts_code=ts_code)
        if df.empty:
            return df

        sort_col = "end_date" if "end_date" in df.columns else "ann_date"
        df = df.sort_values(sort_col, ascending=False)
        return df.head(limit)

    def build_financial_snapshot(self, ts_code: str, limit: int = 8) -> str:
        df = self.get_financial_indicators(ts_code=ts_code, limit=limit)
        if df.empty:
            return f"{ts_code} 未获取到有效财报指标。"

        latest = df.iloc[0]
        prev = df.iloc[1] if len(df) > 1 else latest

        def value_of(row: pd.Series, cols: list[str]) -> float | None:
            for col in cols:
                if col in row and pd.notna(row[col]):
                    try:
                        return float(row[col])
                    except Exception:
                        return None
            return None

        def fmt(v: float | None, digits: int = 2, suffix: str = "") -> str:
            if v is None:
                return "N/A"
            return f"{v:.{digits}f}{suffix}"

        eps_latest = value_of(latest, ["eps", "dt_eps"])
        eps_prev = value_of(prev, ["eps", "dt_eps"])
        roe_latest = value_of(latest, ["roe", "roe_waa"])
        gross_latest = value_of(latest, ["grossprofit_margin"])
        debt_latest = value_of(latest, ["debt_to_assets"])
        ocf_latest = value_of(latest, ["ocfps"])

        eps_delta = None
        if eps_latest is not None and eps_prev is not None:
            eps_delta = eps_latest - eps_prev

        return (
            f"股票代码: {ts_code}\n"
            f"报告期: {latest.get('end_date', latest.get('ann_date', 'N/A'))}\n"
            f"EPS: {fmt(eps_latest)}，环比变化: {fmt(eps_delta)}\n"
            f"ROE: {fmt(roe_latest, suffix='%')}\n"
            f"毛利率: {fmt(gross_latest, suffix='%')}\n"
            f"资产负债率: {fmt(debt_latest, suffix='%')}\n"
            f"每股经营现金流: {fmt(ocf_latest)}"
        )

    def build_news_snapshot(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 10,
    ) -> str:
        news_df = self.get_stock_news(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if news_df.empty:
            return f"{ts_code} 在指定时间区间未检索到相关新闻。"

        lines: list[str] = []
        for idx, row in news_df.reset_index(drop=True).iterrows():
            title = row.get("title", "")
            pub_time = row.get("pub_time", "")
            source = row.get("source", "")
            content = str(row.get("content", "")).replace("\n", " ")[:120]
            lines.append(f"{idx + 1}. [{pub_time}] {title}（{source}） 摘要: {content}")

        return "\n".join(lines)

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

        merged = pd.merge(daily, daily_basic, on=["ts_code", "trade_date"], how="left", suffixes=("", "_basic"))

        for target_col, candidates in {
            "close": ["close", "close_basic", "close_x", "close_y"],
            "vol": ["vol", "vol_basic", "vol_x", "vol_y"],
            "pct_chg": ["pct_chg", "pct_chg_basic", "pct_chg_x", "pct_chg_y"],
        }.items():
            if target_col in merged.columns:
                continue
            for col in candidates:
                if col in merged.columns:
                    merged[target_col] = merged[col]
                    break

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
