# 统一 Agent 系统架构指南

## 概述

这个文档描述了 lianghua 项目中新的统一 Agent 管理系统。该系统解决了"Agent 各管各"的问题，通过集中管理 Prompt 和工作流来实现真正的 Agent 编排。

## 核心问题与解决方案

### 问题
1. **Prompt 分散**: 每个 Agent 硬编码自己的 system prompt，难以维护
2. **Agent 独立**: Agents 各自为政，缺乏统一的运行框架
3. **流程不规范**: 没有标准的 Agent 协作机制
4. **无法复用**: Prompt 和逻辑无法在不同的 Agent 间复用

### 解决方案

我们引入了三个新的核心模块：

```
┌──────────────────────────────────────────────────────────────┐
│               Unified Workflow Engine                        │
│  (统一工作流引擎 - 对外接口，支持不同分析模式)                 │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│              Agent Orchestrator                              │
│  (Agent 编排器 - 管理多个 Agent 的协作和通信)                  │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│    Prompt Manager ← → Agents (BaseAgent 及子类)              │
│  (集中管理所有 Prompt)   (具体的分析 Agent)                  │
└──────────────────────────────────────────────────────────────┘
```

## 模块详解

### 1. Prompt Manager (`prompt_manager.py`)

**职责**: 集中管理所有 Agent 的提示词模板

**核心特性**:
- 每个 Agent 有对应的 `PromptTemplate`
- 支持模板变量渲染 (Horizon, Risk Level 等)
- 支持导出所有 Prompt 到 JSON (便于版本控制和 audit)

**使用示例**:
```python
from lianghua_agents.prompt_manager import PromptManager

# 获取视觉分析 Agent 的提示词
template = PromptManager.get_template("visual_stock_agent")

# 渲染可执行的 system prompt
prompt = PromptManager.render_system_prompt(
    "investment_decision_agent",
    horizon="1-3个月",
    risk_level="中等",
)

# 列出所有可用的模板
agents = PromptManager.list_templates()

# 导出 Prompt 到文件
PromptManager.export_prompts("prompts_backup.json")
```

**可用的 Prompt 模板**:
- `visual_stock_agent` - 技术面分析
- `financial_news_agent` - 基本面与新闻分析
- `investment_decision_agent` - 综合投资决策
- `quant_research_agent` - 量化研究
- `paper_trading_agent` - 模拟交易执行

### 2. Agent Orchestrator (`agent_orchestrator.py`)

**职责**: 统一管理和调度多个 Agent

**核心特性**:
- 单 Agent 运行
- Agent Pipeline (按顺序执行多个 Agent)
- 结果缓存和导出

**使用示例**:
```python
from lianghua_agents.agent_orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# 获取 Agent 实例
agent = orchestrator.get_agent("decision")

# 运行单个 Agent
output = orchestrator.run_single_agent(
    agent_name="decision",
    user_input="这支股票值得投资吗？",
    context={"horizon": "1-3个月", "risk_level": "中等"},
)

# 运行 Agent 流水线
results = orchestrator.run_pipeline(
    agents=["visual", "news", "decision"],
    ts_code="000001.SZ",
    start_date="20260201",
    end_date="20260331",
)

# 查看结果
print(orchestrator.get_result("visual"))
print(orchestrator.export_results())
```

**可用的 Agent**:
- `visual` - VisualStockAgent (技术分析)
- `news` - FinancialNewsAgent (基本面分析)
- `decision` - InvestmentDecisionAgent (综合决策)
- `quant` - QuantResearchAgent (量化分析)

### 3. Workflow Engine (`workflow_engine.py`)

**职责**: 高级工作流界面，支持不同的分析模式

**核心特性**:
- 四种预定义的工作流模式
- 统一的 `WorkflowRequest` 输入
- 一致的 `WorkflowResult` 输出

**工作流模式**:

| 模式 | 英文 | 说明 | 使用场景 |
|------|------|------|---------|
| 单Agent | SINGLE | 仅运行指定的一个 Agent | 特定的分析需求 |
| 技术面 | TECHNICAL | 仅运行视觉/技术面分析 | 短期技术交易 |
| 基本面 | FUNDAMENTAL | 仅运行基本面/新闻分析 | 中期价值分析 |
| 综合 | COMPREHENSIVE | 运行完整流程(技术+基本面+决策) | 完整的投资决策 |

**使用示例**:
```python
from lianghua_agents.workflow_engine import (
    WorkflowRequest,
    WorkflowMode,
    get_workflow_engine,
)

engine = get_workflow_engine()

# 创建工作流请求
request = WorkflowRequest(
    mode=WorkflowMode.COMPREHENSIVE,  # 综合分析
    ts_code="000001.SZ",
    user_prompt="全面分析这支股票，给出投资建议",
    start_date="20260201",
    end_date="20260331",
    horizon="1-3个月",
    risk_level="中等",
    use_rag=True,  # 启用知识库
)

# 运行工作流
result = engine.run(request)

# 检查结果
if result.is_success():
    for agent_name, output in result.results.items():
        print(f"[{agent_name}]: {output}")
else:
    for agent_name, error in result.errors.items():
        print(f"[ERROR {agent_name}]: {error}")

# 导出结果
result_json = engine.orchestrator.export_results()
```

## 数据流

### 完整的分析流程 (COMPREHENSIVE 模式)

```
用户输入
  ↓
WorkflowRequest
  ↓
WorkflowEngine.run()
  ↓
AgentOrchestrator.run_pipeline()
  ├─→ VisualStockAgent (技术分析)
  │    ├─→ 获取 K 线数据
  │    ├─→ 进行技术分析
  │    └─→ 输出技术结论
  │
  ├─→ FinancialNewsAgent (基本面分析)
  │    ├─→ 获取财报数据
  │    ├─→ 获取新闻信息
  │    └─→ 输出基本面结论
  │
  └─→ InvestmentDecisionAgent (综合决策)
       ├─→ 融合技术面和基本面
       ├─→ 应用 PromptManager 的决策 Prompt
       └─→ 输出投资建议
  ↓
WorkflowResult (包含所有分析结果)
```

## 如何使用新系统

### 方式1: 通过 CLI (推荐用于交互式分析)

```bash
# 还是用原来的 CLI 命令
PYTHONPATH=src python examples/cli.py chat -s 000001

# 将来可以增强为使用新的系统
```

### 方式2: 通过统一工作流 (推荐用于程序化分析)

```bash
# 运行统一工作流演示
PYTHONPATH=src python examples/run_unified_workflow.py
```

### 方式3: 在代码中直接调用

```python
from lianghua_agents.workflow_engine import (
    WorkflowRequest,
    WorkflowMode,
    get_workflow_engine,
)

request = WorkflowRequest(
    mode=WorkflowMode.COMPREHENSIVE,
    ts_code="000001.SZ",
    user_prompt="分析这支股票",
)

result = get_workflow_engine().run(request)
```

## BaseAgent 的增强

已更新 `BaseAgent` 以支持 `PromptManager`:

```python
class BaseAgent:
    # 子类可以指定 prompt 模板名称
    prompt_template_name: str | None = None
    
    def __init__(self, system_prompt: str | None = None):
        # 如果有自定义 system_prompt，使用它
        # 否则从 prompt_template_name 查找
        # 最后回退到默认 prompt
        ...
```

**子类可以这样使用**:

```python
class MyAgent(BaseAgent):
    prompt_template_name = "visual_stock_agent"
    
    def get_system_prompt(self, context=None):
        # 自动从 PromptManager 获取
        return super().get_system_prompt(context)
```

## Prompt 版本管理

### 导出所有 Prompt

```python
from lianghua_agents.prompt_manager import PromptManager

# 导出到 JSON 文件（便于版本控制）
PromptManager.export_prompts("prompts_v1.0.json")
```

### 更新 Prompt

在 `prompt_manager.py` 中修改 `PromptTemplate` 的内容，然后重新运行系统即可。

## 性能考量

1. **Agent 缓存**: Orchestrator 缓存 Agent 实例，避免重复创建
2. **结果缓存**: 运行结果缓存在内存中，可通过 `clear_results()` 清空
3. **流水线优化**: 流水线执行按顺序进行，前一个 Agent 的结果可用于后续 Agent

## 扩展指南

### 添加新的 Prompt 模板

在 `PromptManager` 中添加：

```python
class PromptManager:
    MY_NEW_AGENT = PromptTemplate(
        name="my_new_agent",
        version="1.0",
        system_prompt="你是...",
        instructions=[...],
        output_format="...",
        metadata={...},
    )
    
    _TEMPLATES = {
        ...
        "my_new_agent": MY_NEW_AGENT,
    }
```

### 添加新的 Agent 类型

1. 创建新的 Agent 类继承 `BaseAgent`
2. 设置 `prompt_template_name`
3. 在 `AgentOrchestrator.AVAILABLE_AGENTS` 中注册

### 创建新的工作流模式

在 `WorkflowEngine` 中添加新的 `run_xxx()` 方法，然后在 `run()` 中处理对应的 mode。

## 好处总结

✅ **集中管理**: 所有 Prompt 在一个地方，便于维护和 audit  
✅ **易于扩展**: 添加新 Agent 或新 Prompt 很简单  
✅ **标准化**: 统一的工作流和数据格式  
✅ **复用性**: Prompt 和 Agent 可以被多个工作流使用  
✅ **可观测**: 完整的结果记录和错误追踪  
✅ **灵活性**: 支持多种分析模式和自定义参数  

## 向后兼容性

所有现有的 CLI 命令和 API 仍然可用，不会被破坏。新的统一系统是增强性的改进。

---

**下一步**: 查看 `examples/run_unified_workflow.py` 获取完整的使用示例。
