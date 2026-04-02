from __future__ import annotations

from math import sqrt
from typing import Any

import pandas as pd

from .base_agent import AgentState, BaseAgent
from .stock_data import TushareClient


class FactorBacktestAgent(BaseAgent):
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
        if context and context.get("horizon"):
            horizon = str(context["horizon"])
        return (
            "你是量化回测评审智能体。"
            "请严格基于回测指标，给出审慎结论。"
            "输出结构必须包含：\n"
            "1) 因子分层：A(可入池)/B(观察)/C(淘汰)\n"
            "2) 关键证据：IC稳定性、Sharpe、年化、回撤、胜率\n"
            "3) 过拟合信号与样本偏差风险\n"
            "4) 实盘部署建议：仓位、换手上限、滑点容忍\n"
            "5) 下一轮验证计划（窗口滚动、参数扰动）\n"
            f"目标持有周期：{horizon}。不得承诺收益。"
        )

    def post_invoke(self, state: AgentState) -> AgentState:
        output = state.get("output", "")
        state["output"] = f"[FactorBacktestAgent]\n{output}"
        return state

    @staticmethod
    def _max_drawdown(net_value: pd.Series) -> float:
        if net_value.empty:
            return 0.0
        peak = net_value.cummax()
        drawdown = net_value / peak - 1.0
        return float(drawdown.min())

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if pd.isna(value):
                return default
            return float(value)
        except Exception:
            return default

    def _eval_factor(
        self,
        factor_values: pd.Series,
        daily_ret: pd.Series,
        future_ret: pd.Series,
        future_ret_10: pd.Series,
        min_ic_abs: float,
        min_sharpe: float,
        min_win_rate: float,
    ) -> dict[str, float | bool]:
        frame = pd.DataFrame(
            {
                "factor": factor_values,
                "daily_ret": daily_ret,
                "future_ret": future_ret,
            }
        ).dropna()
        if len(frame) < 40:
            return {
                "ic": 0.0,
                "annual_return": 0.0,
                "sharpe": 0.0,
                "win_rate": 0.0,
                "max_drawdown": 0.0,
                "score": 0.0,
                "passed": False,
            }

        ic = self._safe_float(frame["factor"].corr(frame["future_ret"], method="spearman"))
        frame_10 = pd.DataFrame({"factor": factor_values, "future_ret_10": future_ret_10}).dropna()
        ic_10 = self._safe_float(frame_10["factor"].corr(frame_10["future_ret_10"], method="spearman"))
        ic_stability = 1.0 - min(1.0, abs(ic - ic_10) / max(0.01, abs(ic) + abs(ic_10)))
        direction = 1.0 if ic >= 0 else -1.0

        signal_strength = direction * frame["factor"]
        threshold = signal_strength.abs().rolling(20, min_periods=5).median().fillna(0.0)
        position = pd.Series(0.0, index=frame.index)
        position[signal_strength > threshold] = 1.0
        position[signal_strength < -threshold] = -1.0

        turnover = position.diff().abs().fillna(0.0)
        trading_cost = turnover * 0.0008
        strat_ret = position.shift(1).fillna(0.0) * frame["daily_ret"] - trading_cost
        net_value = (1.0 + strat_ret).cumprod()

        mean_ret = self._safe_float(strat_ret.mean())
        std_ret = self._safe_float(strat_ret.std())
        sharpe = mean_ret / std_ret * sqrt(252) if std_ret > 1e-12 else 0.0
        annual_return = self._safe_float(net_value.iloc[-1] ** (252 / max(len(net_value), 1)) - 1.0)
        win_rate = self._safe_float((strat_ret > 0).mean())
        max_dd = self._safe_float(self._max_drawdown(net_value))

        score = (
            abs(ic) * 35
            + abs(ic_10) * 15
            + max(0.0, sharpe) * 20
            + max(0.0, annual_return) * 10
            + max(0.0, win_rate) * 15
            + max(0.0, ic_stability) * 5
        )
        passed = abs(ic) >= min_ic_abs and sharpe >= min_sharpe and win_rate >= min_win_rate

        return {
            "ic": ic,
            "ic_10": ic_10,
            "ic_stability": ic_stability,
            "annual_return": annual_return,
            "sharpe": sharpe,
            "win_rate": win_rate,
            "max_drawdown": max_dd,
            "avg_turnover": self._safe_float(turnover.mean()),
            "score": score,
            "passed": passed,
        }

    def backtest_factors(
        self,
        ts_code: str,
        factor_candidates: list[dict[str, Any]],
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 360,
        holding_days: int = 5,
        min_ic_abs: float = 0.03,
        min_sharpe: float = 0.3,
        min_win_rate: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        df = self.get_tushare_client().get_merged_daily_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if df.empty:
            raise ValueError(f"{ts_code} 无法获取有效行情数据，不能进行因子回测")

        df = df.sort_values("trade_date", ascending=True).reset_index(drop=True)
        daily_ret = df["close"].astype(float).pct_change()
        future_ret = df["close"].astype(float).pct_change(holding_days).shift(-holding_days)
        future_ret_10 = df["close"].astype(float).pct_change(max(holding_days * 2, 10)).shift(-max(holding_days * 2, 10))

        results: list[dict[str, Any]] = []
        for item in factor_candidates:
            values = item.get("values")
            if not isinstance(values, pd.Series):
                continue

            metrics = self._eval_factor(
                factor_values=values.reset_index(drop=True),
                daily_ret=daily_ret,
                future_ret=future_ret,
                future_ret_10=future_ret_10,
                min_ic_abs=min_ic_abs,
                min_sharpe=min_sharpe,
                min_win_rate=min_win_rate,
            )

            results.append(
                {
                    "name": item.get("name", "unknown_factor"),
                    "expression": item.get("expression", ""),
                    "description": item.get("description", ""),
                    "metrics": metrics,
                }
            )

        results.sort(key=lambda x: float(x.get("metrics", {}).get("score", 0.0)), reverse=True)
        effective = [item for item in results if bool(item.get("metrics", {}).get("passed", False))]

        table_lines = [
            f"股票: {ts_code}",
            f"样本区间: {df['trade_date'].iloc[0]} ~ {df['trade_date'].iloc[-1]}",
            f"回测因子数: {len(results)}，有效因子数: {len(effective)}",
            "\n回测结果(按得分排序):",
        ]
        for idx, item in enumerate(results, start=1):
            m = item["metrics"]
            table_lines.append(
                f"{idx}. {item['name']} | IC={m['ic']:.4f}, Sharpe={m['sharpe']:.2f}, "
                f"年化={m['annual_return']:.2%}, 胜率={m['win_rate']:.2%}, "
                f"MDD={m['max_drawdown']:.2%}, 换手={m['avg_turnover']:.2f}, 通过={'是' if m['passed'] else '否'}"
            )

        ai_comment = ""
        try:
            summary_prompt = (
                "\n".join(table_lines)
                + "\n\n请输出："
                "\n- A/B/C层因子池"
                "\n- 每个A级因子的适用行情与禁用条件"
                "\n- 过拟合与样本内偏差信号"
                "\n- 下一轮参数扰动与滚动窗口验证方案"
            )
            ai_comment = self.invoke(summary_prompt, context=context).get("output", "")
        except Exception:
            ai_comment = "[FactorBacktestAgent] AI点评暂不可用，已返回结构化回测结果。"

        return {
            "ts_code": ts_code,
            "results": results,
            "effective_factors": effective,
            "text": "\n".join(table_lines) + "\n\n" + ai_comment,
            "thresholds": {
                "min_ic_abs": min_ic_abs,
                "min_sharpe": min_sharpe,
                "min_win_rate": min_win_rate,
            },
        }
