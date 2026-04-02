"""
Agent 编排器 - 统一管理和运行多个 Agent
支持单 Agent 运行、多 Agent 协作、流水线等
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
import json

from .base_agent import BaseAgent
from .factor_backtest_agent import FactorBacktestAgent
from .factor_mining_agent import FactorMiningAgent
from .factor_pool import FactorPool
from .financial_news_agent import FinancialNewsAgent
from .investment_decision_agent import InvestmentDecisionAgent
from .quant_agent import QuantResearchAgent
from .visual_stock_agent import VisualStockAgent
from .prompt_manager import PromptManager


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    agent_class: type[BaseAgent]
    horizon: str = "1-3个月"
    risk_level: str = "中等"
    strategy: str = "趋势跟随 + 风险控制"
    extra_context: dict[str, Any] = None

    def __post_init__(self):
        if self.extra_context is None:
            self.extra_context = {}


class AgentOrchestrator:
    """Agent 统一编排器"""

    # 预定义的 Agent 配置
    AVAILABLE_AGENTS = {
        "visual": AgentConfig(
            name="visual",
            agent_class=VisualStockAgent,
            extra_context={"agent_type": "technical_analysis"},
        ),
        "news": AgentConfig(
            name="news",
            agent_class=FinancialNewsAgent,
            extra_context={"agent_type": "fundamental_analysis"},
        ),
        "decision": AgentConfig(
            name="decision",
            agent_class=InvestmentDecisionAgent,
            extra_context={"agent_type": "decision_synthesis"},
        ),
        "quant": AgentConfig(
            name="quant",
            agent_class=QuantResearchAgent,
            extra_context={"agent_type": "quantitative_research"},
        ),
        "factor_mining": AgentConfig(
            name="factor_mining",
            agent_class=FactorMiningAgent,
            extra_context={"agent_type": "factor_mining"},
        ),
        "factor_backtest": AgentConfig(
            name="factor_backtest",
            agent_class=FactorBacktestAgent,
            extra_context={"agent_type": "factor_backtest"},
        ),
    }

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}
        self._results: dict[str, Any] = {}

    def get_agent(self, agent_name: str, config: AgentConfig | None = None) -> BaseAgent:
        """获取或创建 Agent 实例"""
        if agent_name in self._agents:
            return self._agents[agent_name]

        if config is None:
            if agent_name not in self.AVAILABLE_AGENTS:
                raise ValueError(
                    f"未知的 Agent: {agent_name}。支持: {list(self.AVAILABLE_AGENTS.keys())}"
                )
            config = self.AVAILABLE_AGENTS[agent_name]

        agent = config.agent_class()
        self._agents[agent_name] = agent
        return agent

    def run_single_agent(
        self,
        agent_name: str,
        user_input: str,
        context: dict[str, Any] | None = None,
        **extra_params,
    ) -> str:
        """运行单个 Agent"""
        agent = self.get_agent(agent_name)
        config = self.AVAILABLE_AGENTS.get(agent_name, AgentConfig(agent_name, BaseAgent))

        # 合并上下文
        full_context = {
            "horizon": config.horizon,
            "risk_level": config.risk_level,
            "strategy": config.strategy,
            **(config.extra_context or {}),
            **(context or {}),
        }

        # 调用 Agent
        result = agent.invoke(user_input=user_input, context=full_context)
        output = result.get("output", "")

        # 保存结果
        self._results[agent_name] = {
            "input": user_input,
            "output": output,
            "context": full_context,
        }

        return output

    def run_pipeline(
        self,
        agents: list[str],
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        user_prompt: str = "",
        context: dict[str, Any] | None = None,
        **extra_params,
    ) -> dict[str, str]:
        """运行 Agent 流水线 - 按顺序执行多个 Agent"""
        results = {}

        if "visual" in agents:
            visual_agent = self.get_agent("visual")
            if isinstance(visual_agent, VisualStockAgent):
                try:
                    results["visual"] = visual_agent.analyze_stock(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date,
                        limit=extra_params.get("price_limit", 120),
                        use_rag=extra_params.get("use_rag", True),
                        rag_top_k=extra_params.get("rag_top_k", 4),
                    )
                except Exception as e:
                    results["visual"] = f"[ERROR] {type(e).__name__}: {e}"

        if "news" in agents:
            news_agent = self.get_agent("news")
            if isinstance(news_agent, FinancialNewsAgent):
                try:
                    results["news"] = news_agent.analyze_stock_with_news_reports(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date,
                        news_limit=extra_params.get("news_limit", 12),
                        finance_limit=extra_params.get("finance_limit", 8),
                        context=context,
                    )
                except Exception as e:
                    results["news"] = f"[ERROR] {type(e).__name__}: {e}"

        # 如果同时运行了 visual 和 news，再运行 decision
        if "decision" in agents and ("visual" in agents or "news" in agents):
            decision_agent = self.get_agent("decision")
            if isinstance(decision_agent, InvestmentDecisionAgent):
                try:
                    results["decision"] = decision_agent.analyze_stock_for_investment(
                        ts_code=ts_code,
                        start_date=start_date,
                        end_date=end_date,
                        price_limit=extra_params.get("price_limit", 120),
                        news_limit=extra_params.get("news_limit", 12),
                        finance_limit=extra_params.get("finance_limit", 8),
                        use_rag=extra_params.get("use_rag", True),
                        rag_top_k=extra_params.get("rag_top_k", 4),
                        context=context,
                    )
                except Exception as e:
                    results["decision"] = f"[ERROR] {type(e).__name__}: {e}"

        self._results.update(results)
        return results

    def run_factor_pipeline(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        context: dict[str, Any] | None = None,
        **extra_params,
    ) -> dict[str, str]:
        """运行因子挖掘 + 回测 + 因子池入池流程。"""
        results: dict[str, str] = {}

        factor_mining_agent = self.get_agent("factor_mining")
        factor_backtest_agent = self.get_agent("factor_backtest")
        if not isinstance(factor_mining_agent, FactorMiningAgent):
            return {"factor_mining": "[ERROR] FactorMiningAgent 初始化失败"}
        if not isinstance(factor_backtest_agent, FactorBacktestAgent):
            return {"factor_backtest": "[ERROR] FactorBacktestAgent 初始化失败"}

        try:
            mining_result = factor_mining_agent.mine_factors(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                limit=extra_params.get("factor_data_limit", 360),
                context=context,
            )
            results["factor_mining"] = mining_result.get("text", "")
        except Exception as exc:
            results["factor_mining"] = f"[ERROR] {type(exc).__name__}: {exc}"
            self._results.update(results)
            return results

        try:
            backtest_result = factor_backtest_agent.backtest_factors(
                ts_code=ts_code,
                factor_candidates=mining_result.get("candidates", []),
                start_date=start_date,
                end_date=end_date,
                limit=extra_params.get("factor_data_limit", 360),
                holding_days=extra_params.get("factor_holding_days", 5),
                min_ic_abs=extra_params.get("factor_min_ic_abs", 0.03),
                min_sharpe=extra_params.get("factor_min_sharpe", 0.3),
                min_win_rate=extra_params.get("factor_min_win_rate", 0.5),
                context=context,
            )
            results["factor_backtest"] = backtest_result.get("text", "")
        except Exception as exc:
            results["factor_backtest"] = f"[ERROR] {type(exc).__name__}: {exc}"
            self._results.update(results)
            return results

        try:
            pool = FactorPool(pool_path=extra_params.get("factor_pool_path", ".factor_pool.json"))
            added = pool.add_effective(
                ts_code=ts_code,
                factor_results=backtest_result.get("results", []),
                min_ic_abs=extra_params.get("factor_min_ic_abs", 0.03),
                min_sharpe=extra_params.get("factor_min_sharpe", 0.3),
                min_win_rate=extra_params.get("factor_min_win_rate", 0.5),
            )

            if added:
                added_names = ", ".join(item.name for item in added)
                results["factor_pool"] = (
                    f"新增有效因子 {len(added)} 个: {added_names}\n\n" + pool.summary(top_n=10)
                )
            else:
                results["factor_pool"] = "本次没有达到阈值的新因子入池。\n\n" + pool.summary(top_n=10)
        except Exception as exc:
            results["factor_pool"] = f"[ERROR] {type(exc).__name__}: {exc}"

        self._results.update(results)
        return results

    def get_results(self) -> dict[str, Any]:
        """获取所有运行结果"""
        return self._results

    def get_result(self, agent_name: str) -> Any:
        """获取特定 Agent 的运行结果"""
        return self._results.get(agent_name)

    def clear_results(self) -> None:
        """清空结果缓存"""
        self._results.clear()

    def export_results(self, output_path: str | None = None) -> str:
        """导出结果为 JSON"""
        data = {
            "timestamp": str(__import__("datetime").datetime.now()),
            "results": self._results,
        }
        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        if output_path:
            __import__("pathlib").Path(output_path).write_text(json_str, encoding="utf-8")
            print(f"✓ 结果已导出到: {output_path}")

        return json_str

    @staticmethod
    def list_agents() -> dict[str, str]:
        """列出所有可用的 Agent"""
        return {
            name: f"{config.agent_class.__name__} - {config.extra_context.get('agent_type', 'unknown')}"
            for name, config in AgentOrchestrator.AVAILABLE_AGENTS.items()
        }

    @staticmethod
    def list_prompts() -> list[str]:
        """列出所有可用的 Prompt 模板"""
        return PromptManager.list_templates()


# 全局 Orchestrator 实例
_global_orchestrator: AgentOrchestrator | None = None


def get_orchestrator() -> AgentOrchestrator:
    """获取全局 Orchestrator 实例"""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AgentOrchestrator()
    return _global_orchestrator
