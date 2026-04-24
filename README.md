# lianghua

一个以多 Agent 协作为核心的量化研究项目，当前代码以 `agent_pools` 为主。

## 项目目标

- 统一管理理论驱动、实证挖掘、自主发现三类 Alpha Agent
- 提供风控、组合、回测等下游模块
- 支持基于 OpenAI Agents SDK / MCP / A2A 的实验性编排

## 当前目录结构（与仓库一致）

```text
lianghua/
├── agent_pools/
│   ├── agents/
│   │   ├── agent_manager.py
│   │   ├── theory_driven/      # momentum / mean_reversion / a2a_client
│   │   ├── empirical/          # data_mining / ml_pattern
│   │   ├── autonomous/         # autonomous_agent
│   │   └── adapters/           # a2a/mcp/storage/feature 适配层
│   ├── alpha_agent_pool/       # AlphaSignalAgent（Qlib + ML）
│   ├── risk_agent_demo/        # RiskSignalAgent 与示例
│   ├── portfolio_agent_demo/   # PortfolioAgent 与示例结果
│   ├── backtest_agent_pool/    # BacktestAgent（Qlib回测）
│   └── qlib_local/             # 本地Qlib数据与完整框架
├── orchestrator_demo/          # 多Agent编排示例
├── examples/
├── data/
├── knowledge/
├── logs/
├── scripts/
├── tests/
├── requirements.txt
└── pyproject.toml
```

## 环境准备

推荐 Python 3.10+。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

部分模块还需要额外依赖（按需安装）：

```bash
pip install openai-agents-sdk a2a python-dotenv
```

可选环境变量：

- `OPENAI_API_KEY`
- `ALPACA_API_KEY`
- `ALPACA_SECRET_KEY`

## 快速运行（按模块）

### 1) 风险 Agent Demo

```bash
python agent_pools/risk_agent_demo/example_usage.py
python agent_pools/risk_agent_demo/test_with_real_data.py
```

### 2) Qlib 本地完整框架 Demo

```bash
python agent_pools/qlib_local/comprehensive_demo.py
python agent_pools/qlib_local/enhanced_visualization_demo.py
```

### 3) Autonomous Agent（MCP Server）

```bash
python agent_pools/agents/autonomous/autonomous_agent.py
```

## 关键模块说明

- `agent_pools/agents/agent_manager.py`
	- 负责统一初始化与调度：`momentum` / `mean_reversion` / `data_mining` / `ml_pattern` / `autonomous`
	- 提供 Alpha 研究工作流聚合与性能摘要

- `agent_pools/agents/theory_driven/momentum_agent.py`
	- 理论驱动动量研究主模块，包含较完整策略流程与回测更新逻辑

- `agent_pools/agents/autonomous/autonomous_agent.py`
	- 自主任务分解、代码生成、策略流产出、MCP工具注册

## 当前状态与注意事项

1. 根目录历史模板仍残留 `src/lianghua_agent` 路径描述；本 README 已按现有实际结构修正。
2. `orchestrator_demo/orchestrator.py` 依赖 OpenAI Agents SDK 与 Alpaca（可选）；若未安装相关依赖会降级或失败。
3. `agent_pools/agents/adapters/*` 使用的 `corepkg` 与 `schema` 位于 `agent_pools/alpha_agent_pool/` 目录下，需保证运行时 `PYTHONPATH` 可解析。

## 建议开发顺序

1. 先打通 `agent_pools/agents` 的研究链路（5类 alpha agent）
2. 再补全 execution 侧（ExecutionAgent + 订单状态回传）
3. 最后做端到端回归测试（alpha → risk → portfolio → backtest）
