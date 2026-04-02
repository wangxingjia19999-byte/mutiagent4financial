"""
统一的 Prompt 管理系统
集中管理所有 Agent 的提示词模板
支持动态渲染和变量替换
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
from pathlib import Path


@dataclass
class PromptTemplate:
    """Prompt 模板类"""
    name: str
    version: str
    system_prompt: str
    instructions: list[str]
    output_format: str
    examples: list[dict[str, str]] = None
    metadata: dict[str, Any] = None

    def render(self, **kwargs) -> str:
        """渲染 prompt 模板，替换变量"""
        prompt = self.system_prompt
        for key, value in kwargs.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "system_prompt": self.system_prompt,
            "instructions": self.instructions,
            "output_format": self.output_format,
            "examples": self.examples or [],
            "metadata": self.metadata or {},
        }


class PromptManager:
    """Prompt 统一管理器"""

    # ============= 看图看线 Agent =============
    VISUAL_STOCK_AGENT = PromptTemplate(
        name="visual_stock_agent",
        version="1.0",
        system_prompt="""你是A股技术面分析智能体，擅长K线形态、支撑阻力、趋势分析。
当前投资周期：{horizon}
风险偏好：{risk_level}
请严格输出结构化分析。""",
        instructions=[
            "1) 技术形态判断：区间/趋势/反转/整理",
            "2) 支撑阻力位：关键价格点",
            "3) 趋势信号（0-100）：上升/下跌/震荡",
            "4) 短期操作建议：买入点/卖出点/观望区间",
            "5) 风险提示（至少2条）：支撑破位/上方压力等",
            "6) 有效期与复盘触发：何时需要重新评估",
        ],
        output_format="使用Markdown格式，清晰的标题和缩进。避免绝对化表述，说明不确定性来源。",
        metadata={"agent_type": "technical_analysis", "category": "charting"},
    )

    # ============= 财报新闻 Agent =============
    FINANCIAL_NEWS_AGENT = PromptTemplate(
        name="financial_news_agent",
        version="1.0",
        system_prompt="""你是A股基本面与事件驱动研究智能体，擅长结合财报与新闻进行判断。
当前关注周期：{horizon}
请输出结构化结论。""",
        instructions=[
            "1) 财报质量判断：盈利能力/现金流/杠杆比率",
            "2) 新闻情绪与事件：利好/中性/利空，重大事件评估",
            "3) 未来走势概率：上涨/震荡/下跌（0-100概率）",
            "4) 主要风险：至少2条关键风险点",
            "5) 交易建议：观望/分批买入/减仓",
            "6) 确定性说明：信息充分度和风险因素",
        ],
        output_format="使用Markdown格式，清晰的结构。避免保证收益，必须给出不确定性说明。",
        metadata={"agent_type": "fundamental_analysis", "category": "news_and_finance"},
    )

    # ============= 投资决策 Agent =============
    INVESTMENT_DECISION_AGENT = PromptTemplate(
        name="investment_decision_agent",
        version="1.0",
        system_prompt="""你是总调投资决策智能体，负责融合技术面和基本面/新闻面的结论，给出最终可执行投资判断。
当前投资周期：{horizon}
风险偏好：{risk_level}
请严格输出结构化分析。""",
        instructions=[
            "1) 综合结论：可投资/谨慎观察/暂不投资",
            "2) 综合评分：0-100分，评分依据",
            "3) 技术面结论摘要：趋势和形态",
            "4) 财报新闻结论摘要：基本面和催化剂",
            "5) 关键共识与冲突点：技术和基本面的一致性",
            "6) 风险清单：至少2条关键风险",
            "7) 操作建议：建仓条件/仓位目标/止损设置",
            "8) 结论有效期与复盘触发条件：何时需要重新评估",
        ],
        output_format="使用Markdown格式，逻辑清晰。必须写出不确定性来源。",
        metadata={"agent_type": "decision_synthesis", "category": "portfolio_decision"},
    )

    # ============= 量化研究 Agent =============
    QUANT_RESEARCH_AGENT = PromptTemplate(
        name="quant_research_agent",
        version="1.0",
        system_prompt="""你是一个量化研究智能体，专注于股票/数字资产的研究分析。
当前偏好策略：{strategy}
风险偏好：{risk_level}
请输出结构化分析。""",
        instructions=[
            "1) 市场状态判断：趋势/震荡/极端情况",
            "2) 可执行信号：做多/做空/观望，信号强度",
            "3) 风险点：止损点/风险评估",
            "4) 仓位建议：初始仓位/金字塔加仓/减仓计划",
            "5) 时间框架：持仓周期和关键时间点",
        ],
        output_format="使用Markdown格式，提供量化指标和数值支撑。",
        metadata={"agent_type": "quantitative_research", "category": "quant"},
    )

    # ============= 模拟交易 Agent =============
    PAPER_TRADING_AGENT = PromptTemplate(
        name="paper_trading_agent",
        version="1.0",
        system_prompt="""你是一个模拟交易执行智能体，负责根据分析结果生成可执行的交易信号。
风险偏好：{risk_level}
资金规模：{account_size}
当前持仓：{current_positions}
请严格输出可执行的交易指令。""",
        instructions=[
            "1) 信号解读：将分析结果转换为买/卖/持有信号",
            "2) 建仓/加仓/减仓计划：具体的股数和价格",
            "3) 风险控制：止损点和止盈点",
            "4) 头寸管理：复合风险评估",
            "5) 调整建议：何时需要调整头寸",
        ],
        output_format="使用JSON格式输出交易指令，便于自动化执行。",
        metadata={"agent_type": "trading_execution", "category": "execution"},
    )

    # 所有模板的字典映射
    _TEMPLATES = {
        "visual_stock_agent": VISUAL_STOCK_AGENT,
        "financial_news_agent": FINANCIAL_NEWS_AGENT,
        "investment_decision_agent": INVESTMENT_DECISION_AGENT,
        "quant_research_agent": QUANT_RESEARCH_AGENT,
        "paper_trading_agent": PAPER_TRADING_AGENT,
    }

    @classmethod
    def get_template(cls, agent_name: str) -> PromptTemplate:
        """获取指定 Agent 的 Prompt 模板"""
        if agent_name not in cls._TEMPLATES:
            raise ValueError(f"未知的 Agent: {agent_name}。支持: {list(cls._TEMPLATES.keys())}")
        return cls._TEMPLATES[agent_name]

    @classmethod
    def list_templates(cls) -> list[str]:
        """列出所有可用的模板"""
        return list(cls._TEMPLATES.keys())

    @classmethod
    def export_prompts(cls, output_path: str | Path) -> None:
        """导出所有 Prompt 到 JSON 文件"""
        output_path = Path(output_path)
        data = {
            "version": "1.0",
            "generated_at": str(Path(__file__).stat().st_mtime),
            "templates": {name: template.to_dict() for name, template in cls._TEMPLATES.items()},
        }
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"✓ Prompts 已导出到: {output_path}")

    @classmethod
    def render_system_prompt(
        cls,
        agent_name: str,
        horizon: str = "1-3个月",
        risk_level: str = "中等",
        strategy: str = "趋势跟随 + 风险控制",
        **kwargs,
    ) -> str:
        """为指定 Agent 渲染完整的 system prompt"""
        template = cls.get_template(agent_name)
        return template.render(
            horizon=horizon,
            risk_level=risk_level,
            strategy=strategy,
            **kwargs,
        )

    @classmethod
    def get_instructions(cls, agent_name: str) -> str:
        """获取指定 Agent 的详细指示"""
        template = cls.get_template(agent_name)
        return "\n".join(template.instructions)

    @classmethod
    def get_output_format(cls, agent_name: str) -> str:
        """获取指定 Agent 的输出格式要求"""
        template = cls.get_template(agent_name)
        return template.output_format


# 全局 PromptManager 实例，便于快速访问
DEFAULT_PROMPT_MANAGER = PromptManager()
