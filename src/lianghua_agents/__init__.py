from importlib import import_module
from typing import Any


__all__ = [
	"BaseAgent",
	"FinancialNewsAgent",
	"InvestmentDecisionAgent",
	"PaperTradingEngine",
	"QuantResearchAgent",
	"build_or_update_rag_index",
	"FinanceKnowledgeRetriever",
	"TushareClient",
	"VisualStockAgent",
	"mcp",
	"cli",
]


def __getattr__(name: str) -> Any:
	if name == "BaseAgent":
		return import_module(".base_agent", __name__).BaseAgent
	if name == "FinancialNewsAgent":
		return import_module(".financial_news_agent", __name__).FinancialNewsAgent
	if name == "InvestmentDecisionAgent":
		return import_module(".investment_decision_agent", __name__).InvestmentDecisionAgent
	if name == "PaperTradingEngine":
		return import_module(".paper_trading", __name__).PaperTradingEngine
	if name == "QuantResearchAgent":
		return import_module(".quant_agent", __name__).QuantResearchAgent
	if name == "build_or_update_rag_index":
		return import_module(".rag_indexer", __name__).build_or_update_rag_index
	if name == "FinanceKnowledgeRetriever":
		return import_module(".retriever", __name__).FinanceKnowledgeRetriever
	if name == "TushareClient":
		return import_module(".stock_data", __name__).TushareClient
	if name == "VisualStockAgent":
		return import_module(".visual_stock_agent", __name__).VisualStockAgent
	if name == "mcp":
		return import_module(".mcp_server", __name__).mcp
	if name == "cli":
		return import_module(".cli", __name__)
	raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
