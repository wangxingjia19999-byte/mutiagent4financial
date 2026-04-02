"""
统一多智能体系统入口。

设计目标：
1. 使用一个统一入口管理多 Agent 协作；
2. 将编排逻辑集中在 orchestrator；
3. 保留简洁请求/响应对象，便于 API 与示例复用。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from .agent_orchestrator import AgentOrchestrator, get_orchestrator


class WorkflowMode(str, Enum):
    """工作流模式。"""

    SINGLE = "single"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    COMPREHENSIVE = "comprehensive"
    FACTOR = "factor"


@dataclass
class WorkflowRequest:
    """多智能体请求对象。"""

    mode: WorkflowMode
    ts_code: str
    user_prompt: str
    start_date: str | None = None
    end_date: str | None = None

    horizon: str = "1-3个月"
    risk_level: str = "中等"
    strategy: str = "趋势跟随 + 风险控制"

    price_limit: int = 120
    news_limit: int = 12
    finance_limit: int = 8
    use_rag: bool = True
    rag_top_k: int = 4

    factor_data_limit: int = 360
    factor_holding_days: int = 5
    factor_min_ic_abs: float = 0.03
    factor_min_sharpe: float = 0.3
    factor_min_win_rate: float = 0.5
    factor_pool_path: str = ".factor_pool.json"

    timeout: int | None = None
    save_results: bool = False
    output_path: str | None = None

    extra_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """多智能体结果对象。"""

    mode: WorkflowMode
    ts_code: str
    status: Literal["success", "partial", "failed"]
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status == "success"

    def get_result(self, agent_name: str) -> Any:
        return self.results.get(agent_name)

    def has_error(self, agent_name: str | None = None) -> bool:
        if agent_name is None:
            return len(self.errors) > 0
        return agent_name in self.errors


class MultiAgentSystem:
    """统一多智能体系统。"""

    def __init__(self, orchestrator: AgentOrchestrator | None = None):
        self.orchestrator = orchestrator or get_orchestrator()

    @staticmethod
    def _build_context(request: WorkflowRequest) -> dict[str, Any]:
        context = {
            "horizon": request.horizon,
            "risk_level": request.risk_level,
            "strategy": request.strategy,
            "custom_prompt": request.user_prompt,
            "ts_code": request.ts_code,
        }
        context.update(request.extra_context)
        return context

    @staticmethod
    def _split_results(results: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
        ok_results: dict[str, str] = {}
        errors: dict[str, str] = {}

        for agent_name, value in results.items():
            if isinstance(value, str) and value.startswith("[ERROR]"):
                errors[agent_name] = value
            else:
                ok_results[agent_name] = value

        return ok_results, errors

    def run(self, request: WorkflowRequest) -> WorkflowResult:
        context = self._build_context(request)

        if request.mode == WorkflowMode.SINGLE:
            agent_name = request.extra_context.get("agent_name", "decision")
            try:
                output = self.orchestrator.run_single_agent(
                    agent_name=agent_name,
                    user_input=request.user_prompt,
                    context=context,
                )
                return WorkflowResult(
                    mode=request.mode,
                    ts_code=request.ts_code,
                    status="success",
                    results={agent_name: output},
                    metadata={"agents": [agent_name]},
                )
            except Exception as exc:
                return WorkflowResult(
                    mode=request.mode,
                    ts_code=request.ts_code,
                    status="failed",
                    errors={agent_name: f"{type(exc).__name__}: {exc}"},
                    metadata={"agents": [agent_name]},
                )

        if request.mode == WorkflowMode.TECHNICAL:
            pipeline_agents = ["visual"]
        elif request.mode == WorkflowMode.FUNDAMENTAL:
            pipeline_agents = ["news"]
        elif request.mode == WorkflowMode.COMPREHENSIVE:
            pipeline_agents = ["visual", "news", "decision"]
        elif request.mode == WorkflowMode.FACTOR:
            factor_results = self.orchestrator.run_factor_pipeline(
                ts_code=request.ts_code,
                start_date=request.start_date,
                end_date=request.end_date,
                context=context,
                factor_data_limit=request.factor_data_limit,
                factor_holding_days=request.factor_holding_days,
                factor_min_ic_abs=request.factor_min_ic_abs,
                factor_min_sharpe=request.factor_min_sharpe,
                factor_min_win_rate=request.factor_min_win_rate,
                factor_pool_path=request.factor_pool_path,
            )

            ok_results, errors = self._split_results(factor_results)
            if not errors:
                status: Literal["success", "partial", "failed"] = "success"
            elif not ok_results:
                status = "failed"
            else:
                status = "partial"

            return WorkflowResult(
                mode=request.mode,
                ts_code=request.ts_code,
                status=status,
                results=ok_results,
                errors=errors,
                metadata={"agents": ["factor_mining", "factor_backtest", "factor_pool"]},
            )
        else:
            return WorkflowResult(
                mode=request.mode,
                ts_code=request.ts_code,
                status="failed",
                errors={"workflow": f"Unknown mode: {request.mode}"},
            )

        pipeline_results = self.orchestrator.run_pipeline(
            agents=pipeline_agents,
            ts_code=request.ts_code,
            start_date=request.start_date,
            end_date=request.end_date,
            user_prompt=request.user_prompt,
            context=context,
            price_limit=request.price_limit,
            news_limit=request.news_limit,
            finance_limit=request.finance_limit,
            use_rag=request.use_rag,
            rag_top_k=request.rag_top_k,
        )

        ok_results, errors = self._split_results(pipeline_results)

        if not errors:
            status: Literal["success", "partial", "failed"] = "success"
        elif not ok_results:
            status = "failed"
        else:
            status = "partial"

        return WorkflowResult(
            mode=request.mode,
            ts_code=request.ts_code,
            status=status,
            results=ok_results,
            errors=errors,
            metadata={"agents": pipeline_agents},
        )


_global_multi_agent_system: MultiAgentSystem | None = None


def get_multi_agent_system() -> MultiAgentSystem:
    """获取全局多智能体系统实例。"""

    global _global_multi_agent_system
    if _global_multi_agent_system is None:
        _global_multi_agent_system = MultiAgentSystem()
    return _global_multi_agent_system
