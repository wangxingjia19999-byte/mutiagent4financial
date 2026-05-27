# lianghua

基于多 Agent 协作的量化投研系统，覆盖 Alpha 信号挖掘、风险控制、组合优化、回测执行到纸交易的全流程。

## 架构概览

```text
                    ┌──────────────────────────────┐
                    │     Orchestrator (编排层)      │
                    └──────────┬───────────────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
   │  Alpha Agent  │   │  Risk Agent   │   │ Portfolio     │
   │  (信号生成)    │   │  (风险控制)    │   │ Agent (组合)  │
   └───────┬───────┘   └───────────────┘   └───────────────┘
           │                                           │
           ▼                                           ▼
   ┌───────────────┐                           ┌───────────────┐
   │  Backtest     │                           │  Execution    │
   │  Agent (回测)  │                           │  Agent (执行)  │
   └───────────────┘                           └───────────────┘
           │                                           │
           └───────────────┬───────────────────────────┘
                           ▼
           ┌───────────────────────────────┐
           │  Memory System (记忆系统)       │
           │  Neo4j + ChromaDB + MCP/A2A    │
           └───────────────────────────────┘
```

## 目录结构

```text
lianghua/
├── agent_pools/
│   ├── alpha_agent_pool/       # Alpha 信号 Agent（核心：Qlib + ML 因子挖掘）
│   │   ├── agents/             # theory_driven / empirical / autonomous 三类 Agent
│   │   ├── adapters/           # A2A / MCP / storage / feature 适配层
│   │   └── schema/             # 信号与策略数据模型
│   ├── risk_agent_demo/        # 风控信号 Agent
│   ├── portfolio_agent_demo/   # 投资组合 Agent
│   ├── backtest_agent_pool/    # 回测 Agent（Qlib 回测框架）
│   ├── execution_agent_demo/   # 执行 Agent（Alpaca 纸交易）
│   ├── qlib_local/             # Qlib 本地模型训练与策略执行
│   └── memory/                 # 记忆系统（Neo4j 图记忆 + ChromaDB 向量库）
├── orchestrator_demo/          # 多 Agent 编排器
├── knowledge/                  # RAG 知识库（ChromaDB + 量化知识文档）
├── data/                       # Tushare 数据拉取
├── trade_journals/             # 纸交易日志
├── run_paper_trading.py        # 纸交易运行器（回测/单次/连续模式）
├── requirements.txt
└── pyproject.toml
```

## 快速开始

### 环境要求

- Python 3.10+
- Neo4j（可选，用于图记忆）
- Redis（可选，用于流处理）

### 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
```

编辑 `.env` 填写必要配置：

| 变量 | 说明 |
|------|------|
| `POE_API_KEY` | Poe API 密钥（LLM 调用） |
| `POE_MODEL` | 模型选择，默认 `GPT-5.4` |
| `TUSHARE_TOKEN` | Tushare 数据源 token |
| `RAG_ENABLE` | 是否启用 RAG，默认 `true` |

### 运行

```bash
# 纸交易 — 回测模式
python run_paper_trading.py --mode backtest --symbol AAPL,MSFT --start 2024-01-01 --end 2024-03-01

# 纸交易 — 单次执行
python run_paper_trading.py --mode once --symbol AAPL,MSFT,GOOGL

# 纸交易 — 连续自动交易（每 300 秒）
python run_paper_trading.py --mode continuous --symbol AAPL,MSFT,GOOGL,TSLA --interval 300

# 风险 Agent Demo
python agent_pools/risk_agent_demo/example_usage.py

# Qlib 本地完整流程
python agent_pools/qlib_local/comprehensive_demo.py
```

## 核心模块

### Alpha Agent Pool

三类 Alpha 挖掘 Agent 的统一管理池：

- **theory_driven** — 基于金融理论（动量、均值回复等）的策略研究
- **empirical** — 数据驱动的因子挖掘与 ML 模式识别
- **autonomous** — 自主任务分解、代码生成、策略产出

通过 MCP/A2A 协议对外暴露信号，由 `alpha_pool_gateway.py` 统一接入。

### Memory System（记忆系统）

多维度记忆与知识管理：

- **Neo4j 图记忆** — 存储 Agent 间关系、策略演化链路
- **ChromaDB 向量库** — RAG 知识检索，支持量化文档语义搜索
- **MCP Server** — 标准化记忆读写接口
- **A2A 协议** — Agent 间记忆共享与协调

### Orchestrator（编排器）

串联 Alpha → Risk → Portfolio → Backtest/Execution 全流程，支持单次运行和连续自动交易模式。

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 框架 | LangChain / LangGraph / CrewAI |
| LLM | OpenAI API（Poe 代理） |
| 量化框架 | Qlib（模型训练与回测） |
| 交易执行 | Alpaca Markets |
| 数据源 | Tushare |
| 向量存储 | ChromaDB |
| 图数据库 | Neo4j |
| 协议 | MCP / A2A |
| 流处理 | Redis |

## 开发路线

1. 完善 Alpha Agent 研究链路（三类 Agent 的策略产出与评估）
2. 补全 Execution Agent（订单管理、持仓同步、异常恢复）
3. 端到端回归测试（Alpha → Risk → Portfolio → Backtest/Execution）
4. 记忆系统深度整合（跨 Agent 经验共享与策略进化）
