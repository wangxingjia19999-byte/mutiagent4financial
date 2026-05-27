# lianghua

基于多 Agent 协作的量化投研系统，覆盖全市场股票筛选、Alpha 信号挖掘、风险控制、组合优化、回测执行到纸交易的全流程。

## 架构概览

```text
                    ┌──────────────────────────────────┐
                    │  Market Universe (全市场股票池)    │
                    │  Alpaca 资产拉取 + 量价筛选        │
                    └──────────────┬───────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │     Orchestrator (编排层)      │
                    │  实时快照预筛 → 流水线调度      │
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
│   ├── market_universe.py        # 全市场股票池（Alpaca 拉取 + 量价筛选）
│   ├── alpha_agent_pool/         # Alpha 信号 Agent（核心：Qlib + ML 因子挖掘）
│   │   ├── agents/               # theory_driven / empirical / autonomous 三类 Agent
│   │   ├── adapters/             # A2A / MCP / storage / feature 适配层
│   │   └── schema/               # 信号与策略数据模型
│   ├── alpha_agent_demo/         # Alpha 信号 Agent（精简版，Orchestrator 直接调用）
│   ├── risk_agent_demo/          # 风控信号 Agent
│   ├── portfolio_agent_demo/     # 投资组合 Agent
│   ├── backtest_agent_pool/      # 回测 Agent（Qlib 回测框架）
│   ├── execution_agent_demo/     # 执行 Agent（Alpaca 纸交易）
│   ├── qlib_local/               # Qlib 本地模型训练与策略执行
│   └── memory/                   # 记忆系统（Neo4j 图记忆 + ChromaDB 向量库）
├── orchestrator_demo/            # 多 Agent 编排器
├── knowledge/                    # RAG 知识库（ChromaDB + 量化知识文档）
├── data/                         # 数据拉取（Tushare + 缓存）
├── trade_journals/               # 纸交易日志
├── run_paper_trading.py          # 纸交易运行器（回测/单次/连续模式）
├── requirements.txt
└── pyproject.toml
```

## 快速开始

### 环境要求

- Python 3.10+
- Alpaca Markets 账号（纸交易即可，免费注册）
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
| `ALPACA_API_KEY` | Alpaca API Key（全市场数据 + 交易） |
| `ALPACA_SECRET_KEY` | Alpaca Secret Key |
| `POE_API_KEY` | Poe API 密钥（LLM 调用） |
| `TUSHARE_TOKEN` | Tushare 数据源 token（A 股可选） |
| `RAG_ENABLE` | 是否启用 RAG，默认 `true` |

### 运行

```bash
# ── 全市场交易 ──
# 回测 S&P 500 级别（~500 只股票）
python run_paper_trading.py --mode backtest --universe sp500 --start 2024-01-01 --end 2024-03-01

# 全市场单次实时交易（~2000 只流动性好的股票）
python run_paper_trading.py --mode once --universe liquid

# 全市场连续自动交易
python run_paper_trading.py --mode continuous --universe nasdaq100 --interval 300

# ── 手工指定股票 ──
python run_paper_trading.py --mode backtest --symbol AAPL,MSFT,GOOGL --start 2024-01-01 --end 2024-03-01

# ── 全量无筛选（谨慎使用，API 调用量大）──
python run_paper_trading.py --mode once --universe all --no-filter

# ── 子模块 Demo ──
python agent_pools/risk_agent_demo/example_usage.py
python agent_pools/qlib_local/comprehensive_demo.py
```

`--universe` 参数说明：

| 值 | 股票数量 | 筛选条件 |
|------|------|------|
| `nasdaq100` | ~100 | 量价筛选后的前 100 只 |
| `sp500` | ~500 | 量价筛选后的前 500 只 |
| `liquid` | ~2000 | 价格 > \$2，日均成交量 > 10 万股 |
| `all` | 全部 | 仅保留主要交易所可交易标的 |

## 核心模块

### Market Universe（全市场股票池）

[market_universe.py](agent_pools/market_universe.py) 负责从 Alpaca 拉取全市场可交易股票：

- 自动获取所有 NYSE / NASDAQ 活跃股票
- 按价格、成交量、交易所过滤（跳过 OTC、仙股等）
- 支持分级范围（nasdaq100 / sp500 / liquid / all）
- 带 24 小时磁盘缓存，避免重复 API 调用

### 实时预筛选

Orchestrator 在全市场实时模式下自动执行两阶段筛选：

1. **Snapshot 预筛** — 用 Alpaca 快照数据按动量 + 成交量快速筛选 top 200 候选
2. **ML 精选** — Alpha Agent 对候选股票做 RSI / MACD / Bollinger 指标计算和模型预测
3. **组合优化** — Portfolio Agent 从信号中选出 top N 持仓（默认 20），等权分配

### Alpha Agent Pool

三类 Alpha 挖掘 Agent 的统一管理池：

- **theory_driven** — 基于金融理论（动量、均值回复等）的策略研究
- **empirical** — 数据驱动的因子挖掘与 ML 模式识别
- **autonomous** — 自主任务分解、代码生成、策略产出

### Memory System（记忆系统）

- **Neo4j 图记忆** — 存储 Agent 间关系、策略演化链路
- **ChromaDB 向量库** — RAG 知识检索，支持量化文档语义搜索
- **MCP / A2A 协议** — Agent 间标准化通信与记忆共享

## 交易模式

| 模式 | 命令 | 说明 |
|------|------|------|
| `backtest` | `--mode backtest` | 历史回测，支持单期和滚动周模式 |
| `once` | `--mode once` | 单次实时交易周期（需开盘时间） |
| `continuous` | `--mode continuous` | 连续自动交易，可按秒级间隔 |

## 技术栈

| 层级 | 技术 |
|------|------|
| Agent 框架 | LangChain / LangGraph / CrewAI |
| LLM | OpenAI API（Poe 代理） |
| 量化框架 | Qlib（模型训练与回测） |
| 市场数据 | Alpaca Markets（美股全市场） |
| 交易执行 | Alpaca Trading API（纸交易 / 实盘） |
| A 股数据 | Tushare |
| 向量存储 | ChromaDB |
| 图数据库 | Neo4j |
| 协议 | MCP / A2A |
| 流处理 | Redis |

## 开发路线

1. 全市场 Alpha 截面排名模型（替代当前逐只独立预测）
2. 行业中性化与风险因子暴露控制
3. Execution Agent 完善（订单分片、TWAP/VWAP 算法执行）
4. 记忆系统深度整合（跨 Agent 经验共享与策略进化）
