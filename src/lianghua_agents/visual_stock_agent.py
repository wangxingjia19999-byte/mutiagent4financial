from __future__ import annotations

import base64
from io import BytesIO
from typing import Any
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .base_agent import BaseAgent
from .stock_data import TushareClient


if TYPE_CHECKING:
    from .retriever import FinanceKnowledgeRetriever


class VisualFusionState(TypedDict, total=False):
    input: str
    context: dict[str, Any]
    chart_base64: str
    snapshot: str
    retrieved_context: str
    technical_view: str
    valuation_view: str
    risk_view: str
    output: str


class VisualStockAgent(BaseAgent):
    def __init__(self, *args, tushare_token: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tushare_client: TushareClient | None = None
        self._tushare_token = tushare_token or self.settings.tushare_token
        self._retriever: FinanceKnowledgeRetriever | None = None
        self._retriever_load_error: str | None = None

    def get_retriever(self) -> FinanceKnowledgeRetriever:
        if self._retriever is None:
            try:
                from .retriever import FinanceKnowledgeRetriever as _FinanceKnowledgeRetriever

                self._retriever = _FinanceKnowledgeRetriever(self.settings)
                self._retriever_load_error = None
            except Exception as exc:
                self._retriever_load_error = str(exc)
                raise
        return self._retriever

    def get_tushare_client(self) -> TushareClient:
        if self._tushare_client is None:
            self._tushare_client = TushareClient(token=self._tushare_token)
        return self._tushare_client

    def get_system_prompt(self, context: dict[str, Any] | None = None) -> str:
        return (
            "你是一名专业A股量化研究员，擅长技术分析与交易风险管理。"
            "请基于给定的图表与结构化数据，判断短期（3-10个交易日）上涨概率。"
            "输出必须包含：\n"
            "1) 趋势判断（多头/震荡/空头）\n"
            "2) 上涨概率（0-100）\n"
            "3) 关键依据（图形、均线、量能、估值）\n"
            "4) 风险提示（至少2条）\n"
            "5) 交易建议（观望/低吸/减仓）\n"
            "注意：不保证收益，避免绝对化表述。"
        )

    def _build_graph(self):
        workflow = StateGraph(VisualFusionState)
        workflow.add_node("retrieve_context", self._retrieve_context_node)
        workflow.add_node("technical_agent", self._technical_node)
        workflow.add_node("valuation_agent", self._valuation_node)
        workflow.add_node("risk_agent", self._risk_node)
        workflow.add_node("fusion_agent", self._fusion_node)

        workflow.add_edge(START, "retrieve_context")
        workflow.add_edge("retrieve_context", "technical_agent")
        workflow.add_edge("technical_agent", "valuation_agent")
        workflow.add_edge("valuation_agent", "risk_agent")
        workflow.add_edge("risk_agent", "fusion_agent")
        workflow.add_edge("fusion_agent", END)
        return workflow.compile()

    def _retrieve_context_node(self, state: VisualFusionState) -> VisualFusionState:
        ts_code = state.get("input", "")
        snapshot = state.get("snapshot", "")
        runtime_context = state.get("context", {})
        use_rag = bool(runtime_context.get("use_rag", True))
        rag_top_k = int(runtime_context.get("rag_top_k", 4))
        if not use_rag:
            return {"retrieved_context": ""}

        query = (
            f"A股 {ts_code} 技术面 估值面 风险面 交易策略。"
            f"参考行情摘要: {snapshot}"
        )
        try:
            retrieved_context = self.get_retriever().retrieve(
                query=query,
                top_k=max(1, rag_top_k),
                ts_code=ts_code,
            )
        except Exception:
            retrieved_context = ""
        return {"retrieved_context": retrieved_context}

    def _invoke_specialist(
        self,
        system_prompt: str,
        user_prompt: str,
        chart_base64: str | None = None,
    ) -> str:
        messages: list[BaseMessage]
        if chart_base64:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=[
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{chart_base64}"},
                        },
                    ]
                ),
            ]
        else:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

        response = self.llm.invoke(messages)
        return self._extract_text(response)

    def _technical_node(self, state: VisualFusionState) -> VisualFusionState:
        chart = state.get("chart_base64", "")
        snapshot = state.get("snapshot", "")
        retrieved_context = state.get("retrieved_context", "")

        system_prompt = (
            "你是技术面子智能体。重点分析趋势、均线结构、量价关系、潜在突破或破位。"
            "输出必须包含：技术结论、上涨概率(0-100)、关键技术依据(至少3条)。"
        )
        user_prompt = (
            f"请基于以下股票信息分析技术面：\n\n{snapshot}\n\n"
            f"可参考资料（RAG检索）:\n{retrieved_context or '无'}"
        )
        technical_view = self._invoke_specialist(system_prompt, user_prompt, chart_base64=chart)
        return {"technical_view": technical_view}

    def _valuation_node(self, state: VisualFusionState) -> VisualFusionState:
        snapshot = state.get("snapshot", "")
        retrieved_context = state.get("retrieved_context", "")

        system_prompt = (
            "你是估值面子智能体。重点依据PE、PB、换手率、量比等判断估值与交易拥挤度。"
            "输出必须包含：估值结论、上涨概率(0-100)、估值依据(至少3条)。"
        )
        user_prompt = (
            f"请基于以下股票信息分析估值面：\n\n{snapshot}\n\n"
            f"可参考资料（RAG检索）:\n{retrieved_context or '无'}"
        )
        valuation_view = self._invoke_specialist(system_prompt, user_prompt)
        return {"valuation_view": valuation_view}

    def _risk_node(self, state: VisualFusionState) -> VisualFusionState:
        snapshot = state.get("snapshot", "")
        retrieved_context = state.get("retrieved_context", "")

        system_prompt = (
            "你是风控面子智能体。重点识别波动风险、回撤风险、流动性风险和情绪反转风险。"
            "输出必须包含：风险等级(低/中/高)、主要风险点(至少3条)、风控建议。"
        )
        user_prompt = (
            f"请基于以下股票信息分析风险面：\n\n{snapshot}\n\n"
            f"可参考资料（RAG检索）:\n{retrieved_context or '无'}"
        )
        risk_view = self._invoke_specialist(system_prompt, user_prompt)
        return {"risk_view": risk_view}

    def _fusion_node(self, state: VisualFusionState) -> VisualFusionState:
        technical_view = state.get("technical_view", "")
        valuation_view = state.get("valuation_view", "")
        risk_view = state.get("risk_view", "")

        system_prompt = (
            "你是总控融合子智能体，负责融合技术面、估值面、风控面结论，并给出唯一交易信号。"
            "输出格式必须严格如下：\n"
            "- 统一信号: 看多/中性/看空\n"
            "- 未来3-10日上涨概率(0-100):\n"
            "- 信心等级(0-100):\n"
            "- 融合依据:\n"
            "- 交易计划(入场/止损/仓位):\n"
            "- 风险声明:"
        )
        user_prompt = (
            "请融合三个子智能体观点，给出最终统一信号。\n\n"
            f"【技术面子智能体】\n{technical_view}\n\n"
            f"【估值面子智能体】\n{valuation_view}\n\n"
            f"【风控面子智能体】\n{risk_view}"
        )
        output = self._invoke_specialist(system_prompt, user_prompt)
        return {"output": output}

    def build_messages(self, user_input: str, context: dict[str, Any] | None = None) -> list[BaseMessage]:
        system_prompt = self.get_system_prompt(context)
        chart_b64 = (context or {}).get("chart_base64")

        if chart_b64:
            return [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=[
                        {"type": "text", "text": user_input},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{chart_b64}"},
                        },
                    ]
                ),
            ]

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input),
        ]

    @staticmethod
    def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()

        if "close" not in frame.columns:
            for alt in ["close_basic", "close_x", "close_y"]:
                if alt in frame.columns:
                    frame["close"] = frame[alt]
                    break
        if "vol" not in frame.columns:
            for alt in ["vol_basic", "vol_x", "vol_y"]:
                if alt in frame.columns:
                    frame["vol"] = frame[alt]
                    break

        required_cols = ["trade_date", "close", "vol"]
        missing = [col for col in required_cols if col not in frame.columns]
        if missing:
            raise ValueError(f"行情数据缺少关键字段: {', '.join(missing)}，当前字段: {list(frame.columns)}")

        frame["trade_date"] = pd.to_datetime(frame["trade_date"], format="%Y%m%d")
        frame = frame.sort_values("trade_date", ascending=True)

        close = frame["close"].astype(float)
        frame["ma5"] = close.rolling(window=5).mean()
        frame["ma10"] = close.rolling(window=10).mean()
        frame["ma20"] = close.rolling(window=20).mean()
        frame["vol_ma5"] = frame["vol"].astype(float).rolling(window=5).mean()
        return frame

    @staticmethod
    def _build_chart_base64(df: pd.DataFrame, ts_code: str) -> str:
        frame = VisualStockAgent._prepare_dataframe(df)
        recent = frame.tail(80)

        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        price_ax, vol_ax = axes

        x = recent["trade_date"]
        price_ax.plot(x, recent["close"].astype(float), label="Close", linewidth=1.5)
        price_ax.plot(x, recent["ma5"], label="MA5", linewidth=1.0)
        price_ax.plot(x, recent["ma10"], label="MA10", linewidth=1.0)
        price_ax.plot(x, recent["ma20"], label="MA20", linewidth=1.0)
        price_ax.set_title(f"{ts_code} Price & Moving Averages")
        price_ax.legend(loc="upper left")
        price_ax.grid(alpha=0.3)

        vol_ax.bar(x, recent["vol"].astype(float), label="Volume", alpha=0.6)
        vol_ax.plot(x, recent["vol_ma5"], label="VOL_MA5", linewidth=1.0)
        vol_ax.legend(loc="upper left")
        vol_ax.grid(alpha=0.3)

        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=160)
        plt.close(fig)
        buffer.seek(0)
        return base64.b64encode(buffer.read()).decode("utf-8")

    @staticmethod
    def _build_snapshot_text(df: pd.DataFrame, ts_code: str) -> str:
        frame = VisualStockAgent._prepare_dataframe(df)
        latest = frame.iloc[-1]
        prev = frame.iloc[-2] if len(frame) > 1 else latest

        close = float(latest["close"])
        prev_close = float(prev["close"])
        daily_change = (close - prev_close) / prev_close * 100 if prev_close else 0.0

        pe = latest.get("pe")
        pb = latest.get("pb")
        turnover_rate = latest.get("turnover_rate")
        volume_ratio = latest.get("volume_ratio")

        def fmt(v: Any, digits: int = 2) -> str:
            if v is None or pd.isna(v):
                return "N/A"
            return f"{float(v):.{digits}f}"

        return (
            f"股票代码: {ts_code}\\n"
            f"最新交易日: {latest['trade_date'].strftime('%Y-%m-%d')}\\n"
            f"收盘价: {close:.2f}，单日涨跌: {daily_change:.2f}%\\n"
            f"MA5/MA10/MA20: {fmt(latest.get('ma5'))}/{fmt(latest.get('ma10'))}/{fmt(latest.get('ma20'))}\\n"
            f"成交量(手): {fmt(latest.get('vol'), 0)}，量比: {fmt(volume_ratio)}\\n"
            f"换手率: {fmt(turnover_rate)}%，PE: {fmt(pe)}，PB: {fmt(pb)}"
        )

    def analyze_stock(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 120,
        use_rag: bool = True,
        rag_top_k: int = 4,
    ) -> str:
        df = self.get_tushare_client().get_merged_daily_data(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=max(limit, 80),
        )
        if df.empty:
            return f"{ts_code} 未获取到可分析数据。"

        chart_base64 = self._build_chart_base64(df, ts_code)
        snapshot = self._build_snapshot_text(df, ts_code)

        result = self.graph.invoke(
            {
                "input": ts_code,
                "context": {"use_rag": use_rag, "rag_top_k": rag_top_k},
                "chart_base64": chart_base64,
                "snapshot": snapshot,
            }
        )
        return result.get("output", "")
