from __future__ import annotations

from typing import Any

import pandas as pd

from .base_agent import AgentState, BaseAgent
from .stock_data import TushareClient


class FactorMiningAgent(BaseAgent):
    def __init__(self, *args, tushare_token: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tushare_client: TushareClient | None = None
        self._tushare_token = tushare_token or self.settings.tushare_token

    def get_tushare_client(self) -> TushareClient:
        if self._tushare_client is None:
            self._tushare_client = TushareClient(token=self._tushare_token)
        return self._tushare_client

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        horizon = "5-20个交易日"
        risk = "中等"
        if context:
            if context.get("horizon"):
                horizon = str(context["horizon"])
            if context.get("risk_level"):
                risk = str(context["risk_level"])
        return (
            "你是A股日频因子挖掘专家，目标是在给定样本中发现稳健、可解释、可复现的短中期因子。"
            "请严格按以下结构输出：\n"
            "1) 候选因子分组：趋势/反转/波动/量价/结构\n"
            "2) 每个因子的经济含义与触发机制\n"
            "3) 因子失效条件（至少2条）\n"
            "4) 去噪与稳健化建议（标准化、截尾、窗口）\n"
            "5) 实盘注意事项（换手、滑点、成本敏感性）\n"
            "必须指出不确定性，不得承诺收益。"
            f"当前目标持有周期：{horizon}；风险偏好：{risk}。"
        )

    def post_invoke(self, state: AgentState) -> AgentState:
        output = state.get("output", "")
        state["output"] = f"[FactorMiningAgent]\n{output}"
        return state

    @staticmethod
    def _zscore(series: pd.Series, window: int = 20) -> pd.Series:
        mean = series.rolling(window, min_periods=max(5, window // 3)).mean()
        std = series.rolling(window, min_periods=max(5, window // 3)).std().replace(0, pd.NA)
        return (series - mean) / std

    @staticmethod
    def _rank_norm(series: pd.Series, window: int = 60) -> pd.Series:
        ranked = series.rolling(window, min_periods=max(10, window // 3)).rank(pct=True)
        return ranked * 2 - 1

    @staticmethod
    def _clip(series: pd.Series, low: float = 0.02, high: float = 0.98) -> pd.Series:
        lower = series.quantile(low)
        upper = series.quantile(high)
        return series.clip(lower=lower, upper=upper)

    def _build_candidates(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        close = df["close"].astype(float)
        vol = df["vol"].astype(float)
        pct = df["pct_chg"].astype(float) / 100.0

        open_px = df["open"].astype(float) if "open" in df.columns else close
        high_px = df["high"].astype(float) if "high" in df.columns else close
        low_px = df["low"].astype(float) if "low" in df.columns else close

        mom_5 = close / close.shift(5) - 1
        mom_20 = close / close.shift(20) - 1
        reversal_5 = -(close / close.shift(5) - 1)
        vol_z_20 = self._zscore(vol, window=20)
        volatility_20 = -pct.rolling(20, min_periods=8).std()
        intraday_strength = (close - open_px) / (high_px - low_px + 1e-6)
        price_volume_corr_20 = pct.rolling(20, min_periods=8).corr(vol.pct_change())
        range_ratio_10 = -(high_px / (low_px + 1e-6) - 1).rolling(10, min_periods=5).mean()
        vol_ma_20 = vol.rolling(20, min_periods=8).mean()
        volume_breakout = (vol / (vol_ma_20 + 1e-6) - 1) * mom_5
        trend_quality = self._zscore(mom_20, 20) * self._zscore(-pct.rolling(20, min_periods=8).std(), 20)
        acceleration_10 = (close / close.shift(10) - 1) - (close.shift(10) / close.shift(20) - 1)
        swing_reversal = -self._zscore(close / close.shift(3) - 1, 20) * self._zscore(
            high_px / (low_px + 1e-6) - 1,
            20,
        )
        liquidity_pressure = self._zscore(pct.abs() * vol.pct_change().fillna(0.0), 20)

        turnover_rate = df["turnover_rate"].astype(float) if "turnover_rate" in df.columns else vol / (vol_ma_20 + 1e-6)
        turnover_stability = -turnover_rate.rolling(20, min_periods=8).std()

        candidate_map = [
            {
                "name": "momentum_5",
                "expression": "close/close.shift(5)-1",
                "description": "短期动量，捕捉5日趋势延续。",
                "values": mom_5,
            },
            {
                "name": "momentum_20",
                "expression": "close/close.shift(20)-1",
                "description": "中期动量，识别20日趋势持续性。",
                "values": mom_20,
            },
            {
                "name": "reversal_5",
                "expression": "-(close/close.shift(5)-1)",
                "description": "短期反转，寻找超涨超跌后的均值回归。",
                "values": reversal_5,
            },
            {
                "name": "volume_zscore_20",
                "expression": "zscore(vol,20)",
                "description": "成交量异常度，衡量资金活跃变化。",
                "values": vol_z_20,
            },
            {
                "name": "low_volatility_20",
                "expression": "-std(pct_chg,20)",
                "description": "低波因子，偏好波动较小的阶段。",
                "values": volatility_20,
            },
            {
                "name": "intraday_strength",
                "expression": "(close-open)/(high-low)",
                "description": "日内强度，反映收盘相对日内区间的位置。",
                "values": intraday_strength,
            },
            {
                "name": "price_volume_corr_20",
                "expression": "corr(pct_chg, vol_change,20)",
                "description": "价量相关性，识别量价共振强度。",
                "values": price_volume_corr_20,
            },
            {
                "name": "range_compression_10",
                "expression": "-mean(high/low-1,10)",
                "description": "振幅压缩因子，识别波动收敛。",
                "values": range_ratio_10,
            },
            {
                "name": "volume_breakout_mom",
                "expression": "(vol/ma(vol,20)-1)*momentum_5",
                "description": "量能放大叠加短动量，捕捉趋势确认。",
                "values": volume_breakout,
            },
            {
                "name": "trend_quality",
                "expression": "zscore(momentum_20)*zscore(-volatility_20)",
                "description": "趋势质量因子，偏好低噪音上涨。",
                "values": trend_quality,
            },
            {
                "name": "acceleration_10",
                "expression": "ret_10 - ret_10_lag",
                "description": "趋势加速度，刻画动量增强/衰减。",
                "values": acceleration_10,
            },
            {
                "name": "swing_reversal",
                "expression": "-zscore(short_ret)*zscore(intraday_range)",
                "description": "摆动反转，偏好高波动后的均值回归。",
                "values": swing_reversal,
            },
            {
                "name": "liquidity_pressure",
                "expression": "zscore(abs(ret)*vol_change)",
                "description": "流动性压力，识别拥挤交易阶段。",
                "values": liquidity_pressure,
            },
            {
                "name": "turnover_stability",
                "expression": "-std(turnover_rate,20)",
                "description": "换手稳定性，偏好交易结构稳定时段。",
                "values": turnover_stability,
            },
        ]

        normalized: list[dict[str, Any]] = []
        for item in candidate_map:
            raw = item["values"].replace([float("inf"), float("-inf")], pd.NA)
            clipped = self._clip(raw)
            item["values"] = self._rank_norm(clipped)
            normalized.append(item)
        return normalized

    def mine_factors(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 360,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        df = self.get_tushare_client().get_merged_daily_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if df.empty:
            raise ValueError(f"{ts_code} 无法获取有效行情数据，不能进行因子挖掘")

        df = df.sort_values("trade_date", ascending=True).reset_index(drop=True)
        candidates = self._build_candidates(df)

        # 过滤全空因子
        valid_candidates = []
        for item in candidates:
            values = item["values"]
            if isinstance(values, pd.Series) and values.notna().sum() >= 30:
                valid_candidates.append(item)

        text_lines = [
            f"股票: {ts_code}",
            f"样本区间: {df['trade_date'].iloc[0]} ~ {df['trade_date'].iloc[-1]}",
            f"候选因子数量: {len(valid_candidates)}",
            "构造说明: 因子已做截尾 + 时序分位归一化，以降低极值和量纲干扰。",
            "候选因子:",
        ]
        for idx, item in enumerate(valid_candidates, start=1):
            text_lines.append(f"{idx}. {item['name']} = {item['expression']} | {item['description']}")

        # 用模型补充解释（失败不影响主流程）
        ai_note = ""
        try:
            prompt = (
                "\n".join(text_lines)
                + "\n\n请输出："
                "\n- A/B/C三级因子分层（A最优）"
                "\n- 每个A级因子对应的适用市场状态"
                "\n- 参数敏感性风险与降噪建议"
                "\n- 下一步应重点回测的3个因子组合"
            )
            ai_note = self.invoke(prompt, context=context).get("output", "")
        except Exception:
            ai_note = "[FactorMiningAgent] AI解释暂不可用，已返回结构化候选因子。"

        return {
            "ts_code": ts_code,
            "data_points": int(len(df)),
            "candidates": valid_candidates,
            "text": "\n".join(text_lines) + "\n\n" + ai_note,
        }
