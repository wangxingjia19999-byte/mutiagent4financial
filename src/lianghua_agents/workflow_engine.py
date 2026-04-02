"""
兼容层：保留历史导入路径。

建议新代码改用：
- lianghua_agents.multi_agent_system.WorkflowRequest
- lianghua_agents.multi_agent_system.WorkflowMode
- lianghua_agents.multi_agent_system.get_multi_agent_system
"""

from .multi_agent_system import (
    MultiAgentSystem as UnifiedWorkflowEngine,
    WorkflowMode,
    WorkflowRequest,
    WorkflowResult,
    get_multi_agent_system,
)


def get_workflow_engine() -> UnifiedWorkflowEngine:
    """兼容旧接口，返回统一多智能体系统实例。"""

    return get_multi_agent_system()
