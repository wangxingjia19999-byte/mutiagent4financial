from __future__ import annotations

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .financial_news_agent import FinancialNewsAgent
from .investment_decision_agent import InvestmentDecisionAgent
from .quant_agent import QuantResearchAgent
from .stock_data import TushareClient
from .visual_stock_agent import VisualStockAgent


load_dotenv()

mcp = FastMCP("lianghua-quant-agent")

_tushare_client: TushareClient | None = None
_quant_agent: QuantResearchAgent | None = None
_visual_agent: VisualStockAgent | None = None
_financial_news_agent: FinancialNewsAgent | None = None
_investment_decision_agent: InvestmentDecisionAgent | None = None


def _get_tushare_client() -> TushareClient:
    global _tushare_client
    if _tushare_client is None:
        _tushare_client = TushareClient()
    return _tushare_client


def _get_quant_agent() -> QuantResearchAgent:
    global _quant_agent
    if _quant_agent is None:
        _quant_agent = QuantResearchAgent()
    return _quant_agent


def _get_visual_agent() -> VisualStockAgent:
    global _visual_agent
    if _visual_agent is None:
        _visual_agent = VisualStockAgent()
    return _visual_agent


def _get_financial_news_agent() -> FinancialNewsAgent:
    global _financial_news_agent
    if _financial_news_agent is None:
        _financial_news_agent = FinancialNewsAgent()
    return _financial_news_agent


def _get_investment_decision_agent() -> InvestmentDecisionAgent:
    global _investment_decision_agent
    if _investment_decision_agent is None:
        _investment_decision_agent = InvestmentDecisionAgent()
    return _investment_decision_agent


@mcp.tool()
def get_stock_basic(exchange: str = "", list_status: str = "L", limit: int = 30) -> list[dict]:
    """获取股票基础信息。list_status: L=上市 D=退市 P=暂停上市"""
    df = _get_tushare_client().get_stock_basic(exchange=exchange, list_status=list_status)
    if df.empty:
        return []
    return df.head(limit).to_dict(orient="records")


@mcp.tool()
def get_stock_daily(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """获取股票日线数据，ts_code 示例: 000001.SZ"""
    df = _get_tushare_client().get_daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    if df.empty:
        return []
    return df.to_dict(orient="records")


@mcp.tool()
def get_stock_news(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """自动获取与股票相关的新闻。支持日期格式 YYYYMMDD 或 YYYY-MM-DD。"""
    df = _get_tushare_client().get_stock_news(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    if df.empty:
        return []
    return df.to_dict(orient="records")


@mcp.tool()
def analyze_stock(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 30,
    strategy: str = "日线趋势+风险控制",
) -> str:
    """拉取 Tushare 数据并调用量化智能体分析。"""
    agent = _get_quant_agent()
    return agent.analyze_stock_with_tushare(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        context={"strategy": strategy},
    )


@mcp.tool()
def analyze_stock_visual(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 120,
    use_rag: bool = True,
    rag_top_k: int = 4,
) -> str:
    """多智能体融合分析：技术面+估值面+风控面，输出统一交易信号。"""
    agent = _get_visual_agent()
    return agent.analyze_stock(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        use_rag=use_rag,
        rag_top_k=rag_top_k,
    )


@mcp.tool()
def analyze_stock_fundamental_news(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    news_limit: int = 12,
    finance_limit: int = 8,
    horizon: str = "1-3个月",
) -> str:
    """融合财报指标与相关新闻进行基本面/事件驱动分析。"""
    agent = _get_financial_news_agent()
    return agent.analyze_stock_with_news_reports(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        news_limit=news_limit,
        finance_limit=finance_limit,
        context={"horizon": horizon},
    )


@mcp.tool()
def analyze_stock_investment_decision(
    ts_code: str,
    start_date: str | None = None,
    end_date: str | None = None,
    price_limit: int = 120,
    news_limit: int = 12,
    finance_limit: int = 8,
    use_rag: bool = True,
    rag_top_k: int = 4,
    horizon: str = "1-3个月",
    risk_level: str = "中等",
) -> str:
    """总调智能体：融合看图看线与财报新闻分析，输出最终投资判断。"""
    agent = _get_investment_decision_agent()
    return agent.analyze_stock_for_investment(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        price_limit=price_limit,
        news_limit=news_limit,
        finance_limit=finance_limit,
        use_rag=use_rag,
        rag_top_k=rag_top_k,
        context={
            "horizon": horizon,
            "risk_level": risk_level,
            "use_rag": use_rag,
            "rag_top_k": rag_top_k,
        },
    )


if __name__ == "__main__":
    mcp.run()
