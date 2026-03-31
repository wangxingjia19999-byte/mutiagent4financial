from typing import Any

from .base_agent import AgentState, BaseAgent
from .stock_data import TushareClient


class QuantResearchAgent(BaseAgent):
    def __init__(self, *args, tushare_token: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tushare_client: TushareClient | None = None
        self._tushare_token = tushare_token or self.settings.tushare_token

    def get_tushare_client(self) -> TushareClient:
        if self._tushare_client is None:
            self._tushare_client = TushareClient(token=self._tushare_token)
        return self._tushare_client

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        strategy = "趋势跟随 + 风险控制"
        if context and context.get("strategy"):
            strategy = str(context["strategy"])

        return (
            "你是一个量化研究智能体，专注于股票/数字资产的研究分析。"
            "请输出结构化分析，包含：\n"
            "1) 市场状态判断\n"
            "2) 可执行信号（做多/做空/观望）\n"
            "3) 风险点\n"
            "4) 仓位建议\n"
            f"当前偏好策略：{strategy}"
        )

    def post_invoke(self, state: AgentState) -> AgentState:
        output = state.get("output", "")
        state["output"] = f"[QuantResearchAgent]\n{output}"
        return state

    def analyze(self, symbol: str, market_snapshot: str, context: dict[str, Any] | None = None) -> str:
        prompt = (
            f"交易标的: {symbol}\n"
            f"市场快照:\n{market_snapshot}\n\n"
            "请给出下一交易周期的分析与建议。"
        )
        result = self.invoke(prompt, context=context)
        return result.get("output", "")

    def analyze_stock_with_tushare(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 30,
        context: dict[str, Any] | None = None,
    ) -> str:
        client = self.get_tushare_client()
        snapshot = client.build_market_snapshot(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        return self.analyze(symbol=ts_code, market_snapshot=snapshot, context=context)
