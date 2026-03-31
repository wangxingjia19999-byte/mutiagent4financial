from typing import Any

from .base_agent import AgentState, BaseAgent
from .financial_news_agent import FinancialNewsAgent
from .visual_stock_agent import VisualStockAgent


class InvestmentDecisionAgent(BaseAgent):
    def __init__(self, *args, tushare_token: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tushare_token = tushare_token or self.settings.tushare_token
        self._visual_agent: VisualStockAgent | None = None
        self._financial_news_agent: FinancialNewsAgent | None = None

    def get_visual_agent(self) -> VisualStockAgent:
        if self._visual_agent is None:
            self._visual_agent = VisualStockAgent(
                settings=self.settings,
                tushare_token=self._tushare_token,
            )
        return self._visual_agent

    def get_financial_news_agent(self) -> FinancialNewsAgent:
        if self._financial_news_agent is None:
            self._financial_news_agent = FinancialNewsAgent(
                settings=self.settings,
                tushare_token=self._tushare_token,
            )
        return self._financial_news_agent

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        horizon = "1-3个月"
        risk_level = "中等"
        custom_prompt = ""
        if context:
            if context.get("horizon"):
                horizon = str(context["horizon"])
            if context.get("risk_level"):
                risk_level = str(context["risk_level"])
            if context.get("custom_prompt"):
                custom_prompt = str(context["custom_prompt"])

        extra_prompt = ""
        if custom_prompt.strip():
            extra_prompt = f"用户额外要求：{custom_prompt.strip()}。"

        return (
            "你是总调投资决策智能体，负责融合技术面和基本面/新闻面的结论，"
            "给出最终可执行投资判断。\n"
            "请严格输出以下结构：\n"
            "1) 综合结论: 可投资/谨慎观察/暂不投资\n"
            "2) 综合评分(0-100):\n"
            "3) 技术面结论摘要:\n"
            "4) 财报新闻结论摘要:\n"
            "5) 关键共识与冲突点:\n"
            "6) 风险清单(至少2条):\n"
            "7) 操作建议(建仓条件/仓位/止损):\n"
            "8) 结论有效期与复盘触发条件:\n"
            "要求：避免绝对化表述，必须写出不确定性来源。"
            f"当前投资周期：{horizon}；风险偏好：{risk_level}。"
            f"{extra_prompt}"
        )

    def post_invoke(self, state: AgentState) -> AgentState:
        output = state.get("output", "")
        state["output"] = f"[InvestmentDecisionAgent]\n{output}"
        return state

    def analyze_stock_for_investment(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        price_limit: int = 120,
        news_limit: int = 12,
        finance_limit: int = 8,
        use_rag: bool = True,
        rag_top_k: int = 4,
        context: dict[str, Any] | None = None,
    ) -> str:
        runtime_context = context or {}

        try:
            visual_view = self.get_visual_agent().analyze_stock(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                limit=price_limit,
                use_rag=bool(runtime_context.get("use_rag", use_rag)),
                rag_top_k=int(runtime_context.get("rag_top_k", rag_top_k)),
            )
        except Exception as exc:
            visual_view = f"看图看线分析暂不可用（已降级继续）：{type(exc).__name__}: {exc}"

        try:
            financial_news_view = self.get_financial_news_agent().analyze_stock_with_news_reports(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                news_limit=news_limit,
                finance_limit=finance_limit,
                context=runtime_context,
            )
        except Exception as exc:
            financial_news_view = f"财报新闻分析暂不可用（已降级继续）：{type(exc).__name__}: {exc}"

        prompt = (
            f"股票代码: {ts_code}\n"
            f"分析区间: {start_date or '默认'} - {end_date or '默认'}\n\n"
            f"【看图看线智能体结论】\n{visual_view}\n\n"
            f"【财报新闻智能体结论】\n{financial_news_view}\n\n"
            "请你作为总调智能体做最终决策。"
        )
        result = self.invoke(prompt, context=runtime_context)
        return result.get("output", "")
