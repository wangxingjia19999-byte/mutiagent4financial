# 统一 Agent 系统 - 快速开始

## 什么是新系统？

lianghua 现在支持一个**统一的 Agent 管理系统**，解决了原来"各 Agent 各自为政"的问题。

**核心改进**:
- ✅ 所有 Prompt 集中管理 (`PromptManager`)
- ✅ 统一的 Agent 编排框架 (`AgentOrchestrator`)  
- ✅ 完整的工作流引擎 (`WorkflowEngine`)
- ✅ 支持多种分析模式（单Agent/技术/基本面/综合）

## 架构

```
用户输入 (Prompt + 参数)
    ↓
WorkflowEngine (高级接口)
    ↓
AgentOrchestrator (编排层)
    ↓
PromptManager ← → 各个 Agent
```

详见 [ARCHITECTURE.md](ARCHITECTURE.md)

## 快速开始

### 1. 查看可用的 Prompt

所有 Agent 的提示词都集中在 `PromptManager` 中：

```bash
PYTHONPATH=src python -c "
from lianghua_agents.prompt_manager import PromptManager
print('可用的 Prompt 模板:')
for name in PromptManager.list_templates():
    print(f'  - {name}')
"
```

### 2. 验证系统框架（推荐先做这个）

运行本地验证测试（**不需要 API 调用**）：

```bash
# 验证所有模块正常加载
PYTHONPATH=src python examples/verify_local.py

# 应该看到:
# ✓ Prompt Manager
# ✓ Agent Orchestrator  
# ✓ Workflow Engine
# ✓ 系统集成
```

### 3. 诊断 API 问题

如果遇到 API 403 错误，运行诊断工具：

```bash
PYTHONPATH=src python examples/diagnose.py

# 诊断工具会：
# 1. 检查环境变量
# 2. 测试 API 连接
# 3. 检查模型可用性
# 4. 建议切换模型
```

### 4. 运行统一工作流（演示）

```bash
# 运行交互式演示
PYTHONPATH=src python examples/run_unified_workflow.py

# 选择要运行的演示模式
# 1. Prompt Manager 演示           ← 推荐先运行（无需 API）
# 2. 单 Agent 模式                 ← 需要 API
# 3. 技术面分析
# 4. 基本面分析
# 5. 综合分析
```

### 3. 在代码中使用

**方式 A: 通过 WorkflowEngine (推荐)**

```python
from lianghua_agents.workflow_engine import (
    WorkflowRequest,
    WorkflowMode,
    get_workflow_engine,
)

# 创建分析请求
request = WorkflowRequest(
    mode=WorkflowMode.COMPREHENSIVE,  # 综合分析
    ts_code="000001.SZ",
    user_prompt="这支股票值得投资吗？",
    start_date="20260201",
    end_date="20260331",
    horizon="1-3个月",
    risk_level="中等",
)

# 运行分析
result = get_workflow_engine().run(request)

# 获取结果
if result.is_success():
    print(result.results)
```

**方式 B: 通过 PromptManager (Prompt 管理)**

```python
from lianghua_agents.prompt_manager import PromptManager

# 获取特定 Agent 的提示词
prompt = PromptManager.render_system_prompt(
    "investment_decision_agent",
    horizon="1-3个月",
    risk_level="中等",
)

# 导出所有 Prompt 到文件
PromptManager.export_prompts("prompts_backup.json")
```

**方式 C: 通过 AgentOrchestrator (Agent 编排)**

```python
from lianghua_agents.agent_orchestrator import get_orchestrator

orchestrator = get_orchestrator()

# 运行单个 Agent
output = orchestrator.run_single_agent(
    agent_name="decision",
    user_input="分析这支股票",
    context={"horizon": "1-3个月"},
)

# 运行多个 Agents（流水线）
results = orchestrator.run_pipeline(
    agents=["visual", "news", "decision"],
    ts_code="000001.SZ",
    start_date="20260201",
    end_date="20260331",
)
```

## 工作流模式

| 模式 | 分析范围 | 适用场景 |
|-----|--------|---------|
| **SINGLE** | 单 Agent | 特定的分析需求 |
| **TECHNICAL** | 技术面 | 短期技术交易 |
| **FUNDAMENTAL** | 基本面 | 中期价值分析 |
| **COMPREHENSIVE** | 完整（技术+基本面+决策） | 完整的投资决策 |

## 关键类

### WorkflowRequest

```python
request = WorkflowRequest(
    mode=WorkflowMode.COMPREHENSIVE,  # 工作流模式
    ts_code="000001.SZ",              # 股票代码
    user_prompt="你的分析问题",        # 用户提问
    start_date="20260201",            # 开始日期
    end_date="20260331",              # 结束日期
    horizon="1-3个月",                 # 投资周期
    risk_level="中等",                 # 风险偏好
    use_rag=True,                     # 启用知识库
    rag_top_k=4,                      # RAG 返回条数
)
```

### WorkflowResult

```python
result = engine.run(request)

# 检查状态
if result.is_success():           # 全部成功
    pass
if result.status == "partial":    # 部分成功
    pass

# 获取结果
result.results                     # 成功的分析结果
result.errors                      # 失败的错误信息
result.metadata                    # 元数据

# 导出到 JSON
json_str = engine.orchestrator.export_results()
```

## 文件结构

```
src/lianghua_agents/
├── prompt_manager.py          # Prompt 集中管理器
├── agent_orchestrator.py      # Agent 编排器
├── workflow_engine.py         # 工作流引擎
├── base_agent.py              # 基础 Agent（已增强）
├── ... (其他各个 Agent)
```

`examples/`
```
├── run_unified_workflow.py    # 统一工作流演示
├── cli.py                     # 原有 CLI（仍可用）
├── ... (其他示例)
```

## 对比：旧 vs 新

### 旧方式（仍可用）

```bash
# 各个 Agent 独立运行
python examples/run_investment_decision_agent.py
python examples/run_quant_agent.py
```

问题：
- 各 Agent 各自管理自己的 prompt
- 难以统一修改 prompt
- Agent 间协作不规范

### 新方式（推荐）

```python
# 通过统一系统运行
from lianghua_agents.workflow_engine import WorkflowRequest, WorkflowMode, get_workflow_engine

request = WorkflowRequest(
    mode=WorkflowMode.COMPREHENSIVE,
    ts_code="000001.SZ",
    user_prompt="分析这支股票",
)

result = get_workflow_engine().run(request)
```

优点：
- ✅ 所有 prompt 集中管理
- ✅ 统一的运行框架
- ✅ 易于维护和扩展
- ✅ 标准的输入/输出格式

## 下一步

1. **运行演示**: `python examples/run_unified_workflow.py`
2. **阅读完整文档**: 查看 [ARCHITECTURE.md](ARCHITECTURE.md)
3. **审查 Prompt**: 在 `prompt_manager.py` 中查看所有 prompt
4. **自定义使用**: 根据需要创建自己的 `WorkflowRequest`

## 向后兼容

所有原有的 CLI 命令仍然可用：

```bash
# 这些仍然可以运行
PYTHONPATH=src python examples/cli.py chat -s 000001
PYTHONPATH=src python examples/run_investment_decision_agent.py
```

新系统是补充性的改进，不会破坏现有的功能。

---

## 🆘 故障排查

### 问题: API 403 "model not available in your region"

**原因**: 你使用的模型在你的地区被限制了

**快速修复**:

```bash
# 1. 运行诊断工具（自动检查和修复）
PYTHONPATH=src python examples/diagnose.py

# 2. 或手动编辑 .env 文件：
nano .env

# 3. 将这一行：
#    OPENROUTER_MODEL=openai/gpt-4o-mini
# 改成：
#    OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# 4. 重新运行
PYTHONPATH=src python examples/run_unified_workflow.py
```

详见: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

### 其他问题

**系统框架没有加载?**
```bash
# 运行本地验证测试
PYTHONPATH=src python examples/verify_local.py
```

**需要完整的故障排查步骤?**
查看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
