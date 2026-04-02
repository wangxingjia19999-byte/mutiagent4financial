from importlib import import_module
from typing import Any


__all__ = [
	"BaseAgent",
	"WorkflowMode",
	"WorkflowRequest",
	"WorkflowResult",
	"MultiAgentSystem",
	"get_multi_agent_system",
	"FinancialNewsAgent",
	"InvestmentDecisionAgent",
	"PaperTradingEngine",
	"QuantResearchAgent",
	"FactorMiningAgent",
	"FactorBacktestAgent",
	"FactorPool",
	"FactorRecord",
	"build_or_update_rag_index",
	"FinanceKnowledgeRetriever",
	"TushareClient",
	"VisualStockAgent",
	"CrewAIIntegrationError",
	"CrewAIWorkflowResult",
	"run_crewai_comprehensive",
	"mcp",
	"cli",
]


def __getattr__(name: str) -> Any:
	if name == "BaseAgent":
		return import_module(".base_agent", __name__).BaseAgent
	if name == "WorkflowMode":
		return import_module(".multi_agent_system", __name__).WorkflowMode
	if name == "WorkflowRequest":
		return import_module(".multi_agent_system", __name__).WorkflowRequest
	if name == "WorkflowResult":
		return import_module(".multi_agent_system", __name__).WorkflowResult
	if name == "MultiAgentSystem":
		return import_module(".multi_agent_system", __name__).MultiAgentSystem
	if name == "get_multi_agent_system":
		return import_module(".multi_agent_system", __name__).get_multi_agent_system
	if name == "FinancialNewsAgent":
		return import_module(".financial_news_agent", __name__).FinancialNewsAgent
	if name == "InvestmentDecisionAgent":
		return import_module(".investment_decision_agent", __name__).InvestmentDecisionAgent
	if name == "PaperTradingEngine":
		return import_module(".paper_trading", __name__).PaperTradingEngine
	if name == "QuantResearchAgent":
		return import_module(".quant_agent", __name__).QuantResearchAgent
	if name == "FactorMiningAgent":
		return import_module(".factor_mining_agent", __name__).FactorMiningAgent
	if name == "FactorBacktestAgent":
		return import_module(".factor_backtest_agent", __name__).FactorBacktestAgent
	if name == "FactorPool":
		return import_module(".factor_pool", __name__).FactorPool
	if name == "FactorRecord":
		return import_module(".factor_pool", __name__).FactorRecord
	if name == "build_or_update_rag_index":
		return import_module(".rag_indexer", __name__).build_or_update_rag_index
	if name == "FinanceKnowledgeRetriever":
		return import_module(".retriever", __name__).FinanceKnowledgeRetriever
	if name == "TushareClient":
		return import_module(".stock_data", __name__).TushareClient
	if name == "VisualStockAgent":
		return import_module(".visual_stock_agent", __name__).VisualStockAgent
	if name == "CrewAIIntegrationError":
		return import_module(".crewai_workflow", __name__).CrewAIIntegrationError
	if name == "CrewAIWorkflowResult":
		return import_module(".crewai_workflow", __name__).CrewAIWorkflowResult
	if name == "run_crewai_comprehensive":
		return import_module(".crewai_workflow", __name__).run_crewai_comprehensive
	if name == "mcp":
		return import_module(".mcp_server", __name__).mcp
	if name == "cli":
		return import_module(".cli", __name__)
	raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
