"""
CrewAI 工作流集成。

提供一个可选的多智能体编排入口，不影响现有 LangGraph 体系。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import os

from .config import AgentSettings


class CrewAIIntegrationError(RuntimeError):
    """CrewAI 集成异常。"""


@dataclass
class CrewAIWorkflowResult:
    """CrewAI 工作流输出。"""

    status: str
    output: str
    metadata: dict


def _prepare_openrouter_for_crewai(settings: AgentSettings) -> None:
    """为 CrewAI/LiteLLM 注入 OpenRouter 兼容环境变量。"""
    os.environ.setdefault("OPENAI_API_KEY", settings.openrouter_api_key)
    os.environ.setdefault("OPENAI_BASE_URL", settings.openrouter_base_url)


def _default_dates(days_back: int = 30) -> tuple[str, str]:
    today = datetime.now()
    start = today - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def run_crewai_comprehensive(
    prompt: str,
    ts_code: str = "000001.SZ",
    horizon: str = "1-3个月",
    risk_level: str = "中等",
    start_date: str | None = None,
    end_date: str | None = None,
    days_back: int = 30,
    verbose: bool = False,
) -> CrewAIWorkflowResult:
    """
    使用 CrewAI 执行综合分析。

    说明：
    - 该入口是可选功能；
    - 依赖 `crewai` 包；
    - 默认采用顺序流程：技术面 -> 基本面 -> 决策汇总。
    """

    try:
        from crewai import Agent, Crew, Process, Task
    except ImportError as exc:
        raise CrewAIIntegrationError(
            "未安装 CrewAI，请先执行: pip install crewai"
        ) from exc

    settings = AgentSettings.from_env()
    _prepare_openrouter_for_crewai(settings)

    if not start_date or not end_date:
        start_date, end_date = _default_dates(days_back=days_back)

    llm_model = settings.model

    technical_analyst = Agent(
        role="技术面分析师",
        goal="基于价格行为与技术信号，给出明确的趋势判断与关键价位。",
        backstory="你擅长趋势、支撑阻力、量价关系与风险边界评估。",
        allow_delegation=False,
        llm=llm_model,
        verbose=verbose,
    )

    fundamental_analyst = Agent(
        role="基本面与资讯分析师",
        goal="提炼财报质量、行业变化与新闻催化，评估基本面方向。",
        backstory="你专注财务健康度、业务变化、政策与舆情风险。",
        allow_delegation=False,
        llm=llm_model,
        verbose=verbose,
    )

    chief_investor = Agent(
        role="投资决策官",
        goal="融合技术面和基本面，形成可执行、可复盘的投资方案。",
        backstory="你强调证据链、仓位纪律、止损机制与不确定性管理。",
        allow_delegation=False,
        llm=llm_model,
        verbose=verbose,
    )

    tech_task = Task(
        description=(
            "请对股票 {ts_code} 做技术面分析。\n"
            "分析区间：{start_date} ~ {end_date}\n"
            "用户问题：{prompt}\n"
            "输出要求：\n"
            "1) 趋势判断（上涨/震荡/下跌）\n"
            "2) 关键价位（支撑/阻力）\n"
            "3) 信号强弱与不确定性\n"
            "4) 风险提示"
        ),
        expected_output="一份结构化技术分析结论，200-400字。",
        agent=technical_analyst,
    )

    fundamental_task = Task(
        description=(
            "请对股票 {ts_code} 做基本面/新闻面分析。\n"
            "分析区间：{start_date} ~ {end_date}\n"
            "用户问题：{prompt}\n"
            "输出要求：\n"
            "1) 业务与财务质量观察\n"
            "2) 近期新闻/事件影响\n"
            "3) 机会与风险清单\n"
            "4) 不确定性来源"
        ),
        expected_output="一份结构化基本面结论，200-400字。",
        agent=fundamental_analyst,
    )

    decision_task = Task(
        description=(
            "你将综合前两位分析师结果，对股票 {ts_code} 给出最终投资建议。\n"
            "用户问题：{prompt}\n"
            "投资周期：{horizon}；风险偏好：{risk_level}\n"
            "必须输出：\n"
            "1) 结论（可投资/谨慎观察/暂不投资）\n"
            "2) 评分（0-100）\n"
            "3) 仓位建议\n"
            "4) 止损与复盘触发条件\n"
            "5) 关键不确定性"
        ),
        expected_output="一份可执行的最终投资方案，300-500字。",
        agent=chief_investor,
        context=[tech_task, fundamental_task],
    )

    crew = Crew(
        agents=[technical_analyst, fundamental_analyst, chief_investor],
        tasks=[tech_task, fundamental_task, decision_task],
        process=Process.sequential,
        verbose=verbose,
    )

    result = crew.kickoff(
        inputs={
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date,
            "prompt": prompt,
            "horizon": horizon,
            "risk_level": risk_level,
        }
    )

    return CrewAIWorkflowResult(
        status="success",
        output=str(result),
        metadata={
            "framework": "crewai",
            "model": llm_model,
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
