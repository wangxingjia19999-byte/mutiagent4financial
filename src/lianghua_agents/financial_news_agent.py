from typing import Any

from .base_agent import AgentState, BaseAgent
from .stock_data import TushareClient


class FinancialNewsAgent(BaseAgent):
    def __init__(self, *args, tushare_token: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tushare_client: TushareClient | None = None
        self._tushare_token = tushare_token or self.settings.tushare_token

    def get_tushare_client(self) -> TushareClient:
        if self._tushare_client is None:
            self._tushare_client = TushareClient(token=self._tushare_token)
        return self._tushare_client

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        horizon = "1-3个月"
        if context and context.get("horizon"):
            horizon = str(context["horizon"])

        return (
            "你是A股基本面与事件驱动研究智能体，擅长结合财报与新闻进行判断。"
            "请输出结构化结论，必须包含：\n"
            "1) 财报质量判断（盈利能力/现金流/杠杆）\n"
            "2) 新闻情绪与事件影响（利好/中性/利空）\n"
            "3) 未来走势概率（上涨/震荡/下跌，给出0-100概率）\n"
            "4) 主要风险（至少2条）\n"
            "5) 交易建议（观望/分批买入/减仓）\n"
            "注意避免保证收益，给出不确定性说明。"
            f"当前关注周期：{horizon}"
        )

    def post_invoke(self, state: AgentState) -> AgentState:
        output = state.get("output", "")
        state["output"] = f"[FinancialNewsAgent]\n{output}"
        return state

    def analyze_stock_with_news_reports(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        news_limit: int = 12,
        finance_limit: int = 8,
        context: dict[str, Any] | None = None,
    ) -> str:
        client = self.get_tushare_client()
        financial_snapshot = client.build_financial_snapshot(ts_code=ts_code, limit=finance_limit)
        news_snapshot = client.build_news_snapshot(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=news_limit,
        )

        prompt = (
            f"股票代码: {ts_code}\n\n"
            f"【财报指标摘要】\n{financial_snapshot}\n\n"
            f"【相关新闻摘要】\n{news_snapshot}\n\n"
            "请基于以上信息进行综合分析，优先关注："
            "盈利质量变化、现金流健康度、新闻事件持续性、潜在预期差。"
        )
        result = self.invoke(prompt, context=context)
        return result.get("output", "")
