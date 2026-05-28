# Lianghua (量化) — 多 Agent 协作量化投研系统

> 基于 LLM 驱动的多智能体协同框架，覆盖**全市场筛选 → Alpha 挖掘 → 风险控制 → 组合优化 → 回测执行 → 纸交易**的全自动量化投研流水线，集成 **Neo4j 图记忆**与 **ChromaDB RAG 知识库**，实现策略的持续学习与进化。

---

## 1. 项目背景与动机

### 1.1 传统量化投研的痛点

| 痛点 | 描述 |
|------|------|
| 流程割裂 | 数据获取、因子挖掘、回测、交易执行分散在多个工具中，缺乏统一编排 |
| 知识流失 | 每次策略迭代从零开始，历史经验、失败教训无法沉淀复用 |
| 人力瓶颈 | 因子挖掘依赖人工经验，难以系统性地探索海量因子空间 |
| 响应滞后 | 人工完成"数据→分析→决策→执行"循环耗时长，错过交易窗口 |

### 1.2 本系统的解决思路

- **LLM 驱动的多 Agent 协作** — 每个 Agent 专注一个环节，通过 Orchestrator 统一调度
- **图记忆系统 (Neo4j)** — 策略表现、失败教训、市场规律自动沉淀为结构化知识图谱
- **RAG 知识库 (ChromaDB)** — 量化论文（Alpha101）向量化，Agent 实时检索学术研究成果
- **全自动流水线** — 从全市场拉取到订单执行，一键完成

---

## 2. 系统架构

### 2.1 整体架构图

```text
                         ┌──────────────────────────────────────┐
                         │        Market Universe (全市场股票池)   │
                         │    Alpaca API 拉取 + 量价流动性筛选     │
                         │    覆盖 NYSE / NASDAQ 全市场标的       │
                         └──────────────┬───────────────────────┘
                                        ▼
                         ┌──────────────────────────────────────┐
                         │       Orchestrator (编排调度层)        │
                         │   ┌──────────────────────────────┐   │
                         │   │  快照预筛：动量 + 成交量 Top-N  │   │
                         │   │  RAG 预查询：检索相关论文知识    │   │
                         │   │  记忆查询：加载历史策略教训       │   │
                         │   └──────────────────────────────┘   │
                         └──────────┬───────────────────────────┘
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Alpha Agent    │ │  Risk Agent     │ │ Portfolio Agent │
    │  (信号生成)      │ │  (风险控制)      │ │  (组合优化)      │
    │                 │ │                 │ │                 │
    │ • Qlib ML 模型  │ │ • VaR/CVaR 计算 │ │ • 均值-方差优化  │
    │ • 158 因子计算  │ │ • 最大回撤监控   │ │ • 行业中性化     │
    │ • IC/IR 评估    │ │ • 流动性风险评估 │ │ • 仓位权重分配   │
    │ • RAG 因子参考  │ │ • 相关性风险     │ │ • 退出信号生成   │
    └────────┬────────┘ └─────────────────┘ └────────┬────────┘
             │                                       │
             ▼                                       ▼
    ┌─────────────────┐                   ┌─────────────────┐
    │ Backtest Agent  │                   │ Execution Agent │
    │  (回测评估)      │                   │  (订单执行)      │
    │                 │                   │                 │
    │ • Qlib 回测引擎 │                   │ • Alpaca 纸交易  │
    │ • 滚动周验证    │                   │ • 订单分片       │
    │ • 绩效归因分析  │                   │ • 滑点控制       │
    │ • 可视化报告    │                   │ • 实时风控       │
    └────────┬────────┘                   └────────┬────────┘
             │                                       │
             └───────────────┬───────────────────────┘
                             ▼
             ┌──────────────────────────────────────┐
             │       Memory System (记忆与知识层)      │
             │  ┌────────────┐  ┌────────────────┐   │
             │  │  Neo4j     │  │  ChromaDB      │   │
             │  │  图记忆     │  │  RAG 向量库    │   │
             │  │            │  │                │   │
             │  │ • 策略演化 │  │ • Alpha101 论文│   │
             │  │ • 失败教训 │  │ • 因子公式检索 │   │
             │  │ • Agent 关系│ │ • 学术语义搜索 │   │
             │  └────────────┘  └────────────────┘   │
             │       MCP / A2A Agent 间通信协议       │
             └──────────────────────────────────────┘
```

### 2.2 数据流时序

```text
用户命令
  │
  ▼
[1] Market Universe ──► 拉取全市场股票 (Alpaca API)
  │
  ▼
[2] Orchestrator ──► 快照预筛 (动量+成交量) → RAG 查询 → 记忆查询
  │
  ├─► [3] Alpha Agent ──► Qlib ML 预测 → 因子信号输出
  ├─► [4] Risk Agent  ──► 波动率/VaR/回撤 → 风险等级输出
  ├─► [5] Portfolio   ──► 信号+风险 → 权重分配 → 订单生成
  │
  ▼
[6] Backtest Agent / Execution Agent ──► 回测报告 / 实盘下单
  │
  ▼
[7] Memory System ──► 存储策略表现、教训 → Neo4j 知识图谱
```

---

## 3. 核心模块详解

### 3.1 Market Universe — 全市场股票池

负责从 Alpaca Markets 拉取全市场可交易标的，是整个流水线的数据入口。

| 特性 | 说明 |
|------|------|
| 覆盖范围 | NYSE、NASDAQ 全市场活跃股票 |
| 筛选逻辑 | 剔除 OTC、仙股（<$2）、日均成交量 < 10 万股 |
| 分级范围 | `nasdaq100`(≈100只) / `sp500`(≈500只) / `liquid`(≈2000只) / `all` |
| 缓存策略 | 24 小时磁盘缓存，减少 API 调用 |

### 3.2 Orchestrator — 多 Agent 编排器

系统的中枢调度层，负责串联各 Agent 的执行顺序与数据传递。

**两阶段预筛选（实时模式）**
1. **Snapshot 快照预筛** — 通过 Alpaca 快照 API，按动量绝对值 × log(成交量) 打分，选出 Top 200 候选
2. **ML 精选** — Alpha Agent 对候选股票计算 RSI / MACD / Bollinger 等 158 个因子，模型预测排序

**RAG & 记忆增强**
- 执行前自动查询 Alpha101 论文获取相关因子构建方法
- 查询 Neo4j 历史教训（过拟合、回撤等），辅助决策
- 执行后自动存储反思到记忆系统

### 3.3 Alpha Agent — 信号生成引擎

核心的 Alpha 信号挖掘 Agent，集成 Qlib 量化框架。

**三类子 Agent**
| 类型 | 方法 | 适用场景 |
|------|------|---------|
| **theory_driven** | 动量、均值回复、低波动等经典金融理论 | 可解释性强，适合实盘 |
| **empirical** | 数据驱动的 ML 因子挖掘、模式识别 | 发现非线性规律 |
| **autonomous** | LLM 自主任务分解、代码生成、策略产出 | 探索新因子空间 |

**核心能力**
- 基于 Qlib Alpha158 的 158 个标准化因子计算
- IC (Information Coefficient) / IR (Information Ratio) 评估
- 线性模型 / LightGBM / GRU / TabNet 多模型支持
- RAG 实时检索 Alpha101 论文学术参考

### 3.4 Risk Agent — 风控系统

多维度的风险评估，在组合构建前提供风控信号。

| 风险维度 | 指标 | 说明 |
|----------|------|------|
| 市场风险 | Volatility, Beta | 波动率、市场敏感性 |
| 尾部风险 | VaR (95%), CVaR | 极端损失估计 |
| 回撤风险 | Max Drawdown | 历史最大回撤 |
| 流动性风险 | 成交量、买卖价差 | 变现能力评估 |
| 相关性风险 | 组合平均相关性 | 分散化程度 |

### 3.5 Portfolio Agent — 组合优化

将 Alpha 信号 + 风险信号转化为可执行的投资组合。

- **信号融合** — Alpha 得分 × 风险折扣系数
- **权重分配** — 等权 / 风险平价 / 均值-方差优化
- **约束条件** — 最大持仓数、单票上限、行业上限
- **退出信号** — 识别持仓中应卖出的标的

### 3.6 Backtest Agent — 回测引擎

基于 Qlib 回测框架的完整历史模拟。

- **Standard 回测** — 固定训练/测试区间
- **Rolling Weekly 回测** — 每周滚动重训，避免前视偏差
- **绩效报告** — 总收益、Sharpe、最大回撤、波动率
- **Long-Short 回测** — 多空组合模拟

### 3.7 Execution Agent — 交易执行

对接 Alpaca Trading API 的订单执行层。

- **纸交易 (Paper Trading)** — 无风险模拟实盘
- **订单类型** — 市价单、限价单、止损单
- **风控** — 开盘时间检查、账户余额校验
- **日志** — 完整的 Trade Journal 记录

### 3.8 Memory System — 记忆与知识系统

让 Agent 具备"记忆"和"学习"能力的关键模块。

```text
┌─────────────────────────────────────────────────────┐
│                 Memory System                        │
│                                                      │
│  ┌──────────────────┐    ┌──────────────────────┐    │
│  │  Neo4j 图记忆     │    │  ChromaDB RAG 向量库  │    │
│  │                  │    │                      │    │
│  │ 节点类型：        │    │ 知识来源：            │    │
│  │ • Agent          │    │ • Alpha101 论文 (PDF) │    │
│  │ • Strategy       │    │ • 60 个文本片段       │    │
│  │ • Issue          │    │ • 语义向量索引        │    │
│  │ • Lesson         │    │                      │    │
│  │ • Memory         │    │ 查询示例：            │    │
│  │                  │    │ "momentum factor      │    │
│  │ 关系类型：        │    │  construction"       │    │
│  │ • PROPOSED       │    │ "Sharpe ratio         │    │
│  │ • ENCOUNTERED    │    │  analysis"            │    │
│  │ • LEARNED        │    │                      │    │
│  │ • RESOLVES       │    │ 自动构建：            │    │
│  │ • SIMILAR_TO     │    │ 首次使用时从 PDF      │    │
│  │                  │    │ 自动构建向量索引      │    │
│  └──────────────────┘    └──────────────────────┘    │
│                                                      │
│  Agent 调用接口:                                      │
│  agent_memory_client.py  (同步, 无需启动服务)          │
│  agent_rag_client.py      (自动索引, 开箱即用)         │
└─────────────────────────────────────────────────────┘
```

**记忆存储示例**
```
Agent: AlphaResearchAgent
Strategy: momentum_factor_v1
Issue: overfitting on small sample
Lesson: Use walk-forward validation with ≥500 data points
→ Neo4j 节点自动关联, 下次遇到 "overfitting" 时自动检索
```

---

## 4. 快速开始

### 4.1 环境要求

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ | 推荐 3.12 |
| Alpaca Markets | 免费账号 | 纸交易 + 全市场数据 |
| Neo4j | 5.x (可选) | 图记忆功能需要 |
| Redis | 6.x (可选) | 流处理功能需要 |

### 4.2 安装

```bash
git clone <repo-url>
cd lianghua
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4.3 配置

```bash
cp .env.example .env
```

编辑 `.env` 填写必要配置：

| 变量 | 说明 | 必须 |
|------|------|------|
| `ALPACA_API_KEY` | Alpaca API Key | ✅ |
| `ALPACA_SECRET_KEY` | Alpaca Secret Key | ✅ |
| `POE_API_KEY` | Poe API 密钥 (LLM) | ✅ |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `NEO4J_URI` | Neo4j 连接地址 | 可选 |
| `NEO4J_USER` | Neo4j 用户名 | 可选 |
| `NEO4J_PASSWORD` | Neo4j 密码 | 可选 |
| `TUSHARE_TOKEN` | Tushare A 股数据 | 可选 |

### 4.4 运行

```bash
# ── 主入口 ──

# 回测 S&P 500 级别 (~500 只股票，含 RAG + 记忆)
python run_paper_trading.py --mode backtest --universe sp500 --start 2024-01-01 --end 2024-03-01

# 全市场单次实时交易
python run_paper_trading.py --mode once --universe liquid

# 全市场连续自动交易
python run_paper_trading.py --mode continuous --universe nasdaq100 --interval 300

# 手工指定股票
python run_paper_trading.py --mode backtest --symbol AAPL,MSFT,GOOGL --start 2024-01-01 --end 2024-03-01

# 滚动周回测 (避免前视偏差)
python run_paper_trading.py --mode backtest --symbol AAPL,MSFT --start 2024-01-01 --end 2024-03-01 --rolling

# 禁用 RAG / 记忆
python run_paper_trading.py --mode backtest --universe sp500 --no-rag --no-memory

# ── 子模块 Demo ──
python agent_pools/alpha_agent_pool/alpha_research_agent.py  # Alpha 因子研究
python agent_pools/risk_agent_demo/example_usage.py           # 风控示例
```

### 4.5 `--universe` 参数

| 值 | 股票数量 | 筛选条件 |
|------|------|------|
| `nasdaq100` | ≈100 | 快照打分 Top 100 |
| `sp500` | ≈500 | 快照打分 Top 500 |
| `liquid` | ≈2000 | 价格 > $2，日均成交 > 10 万股 |
| `all` | 全部 | 仅保留 NYSE/NASDAQ 主要交易所标的 |

---

## 5. 技术栈总览

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **Agent 框架** | OpenAI SDK / LangChain | LLM 驱动的 Agent 推理与工具调用 |
| **大语言模型** | GPT-4o / Claude (Poe 代理) | Agent 的"大脑" |
| **量化框架** | Qlib (Microsoft) | 158 标准化因子 + ML 模型 + 回测引擎 |
| **市场数据** | Alpaca Markets API | 美股全市场实时/历史数据 |
| **交易执行** | Alpaca Trading API | 纸交易 (模拟) / 实盘 |
| **图数据库** | Neo4j | Agent 记忆图谱存储 |
| **向量数据库** | ChromaDB | RAG 知识库语义检索 |
| **通信协议** | MCP / A2A | Agent 间标准化通信 |
| **A 股数据** | Tushare | 国内股票数据接入 |
| **数据缓存** | Disk Cache (24h) | 减少 API 重复调用 |

---

## 6. 项目亮点

### 6.1 技术创新

| 亮点 | 说明 |
|------|------|
| **LLM + 量化融合** | 不是简单的 LLM 包装，而是让 LLM 真正参与因子设计、策略决策 |
| **Agent-as-Tool** | 每个 Agent 既可作为独立工具运行，也可被编排器作为子工具调度 |
| **图记忆系统** | 策略经验以知识图谱形式沉淀，跨任务复用 |
| **RAG 增强** | Agent 决策前自动检索 Alpha101 学术论文，让"理论指导实践" |
| **滚动周验证** | 严格的 Walk-Forward 回测，避免前视偏差 |
| **全市场覆盖** | 不局限于几只股票，真正实现全市场选股 |

### 6.2 工程亮点

| 亮点 | 说明 |
|------|------|
| **统一入口** | `run_paper_trading.py` 一个命令覆盖所有模式 |
| **优雅降级** | Neo4j/Qlib 不可用时自动切换 Mock 模式，不影响核心流程 |
| **模块解耦** | 每个 Agent 独立可测试，通过 Orchestrator 松耦合 |
| **实时快筛** | 全市场 2000+ 股票秒级预筛选，保证实时交易可行性 |
| **RAG 自动构建** | 首次使用时自动从 PDF 构建向量索引，零配置 |

---

## 7. 目录结构

```text
lianghua/
├── run_paper_trading.py              # 主入口 (回测/实时/连续交易)
│
├── orchestrator_demo/                # 多 Agent 编排调度层
│   └── orchestrator.py               # Orchestrator 中枢调度器
│
├── agent_pools/                      # Agent 池
│   ├── market_universe.py            # 全市场股票池拉取
│   ├── poe_config.py                 # LLM (Poe) 配置
│   │
│   ├── alpha_agent_pool/             # Alpha Agent 核心
│   │   ├── agents/                   # 3 类子 Agent
│   │   │   ├── theory_driven/        #   理论驱动 (动量/均值回复)
│   │   │   ├── empirical/            #   数据驱动 (ML 挖掘)
│   │   │   └── autonomous/           #   自主探索 (LLM 生成)
│   │   ├── adapters/                 # A2A/MCP 适配层
│   │   ├── local_agents.py           # Agent SDK 实现
│   │   └── alpha_research_agent.py   # Alpha 研究 Agent Demo
│   │
│   ├── alpha_agent_demo/             # Alpha 精简版
│   ├── risk_agent_demo/              # 风控 Agent
│   ├── portfolio_agent_demo/         # 组合优化 Agent
│   ├── backtest_agent_pool/          # 回测 Agent (Qlib)
│   ├── execution_agent_demo/         # 交易执行 Agent (Alpaca)
│   ├── qlib_local/                   # Qlib 本地模型
│   │
│   └── memory/                       # 记忆与知识系统
│       ├── agent_memory_client.py    #   Neo4j 同步客户端
│       ├── agent_rag_client.py       #   ChromaDB RAG 客户端
│       ├── database.py               #   异步数据库操作
│       ├── memory_server.py          #   MCP 记忆服务
│       ├── unified_database_manager.py
│       └── interface.py              #   MCP 客户端接口
│
├── knowledge/                        # 知识文档
│   └── 1601.00991v3.pdf             # Alpha101 开创性论文
│
├── data/                             # 数据缓存
├── trade_journals/                   # 交易日志
├── requirements.txt
└── pyproject.toml
```

---

## 8. 开发路线图

### Phase 1 — 已完成 ✅
- [x] 多 Agent 协作框架 (Alpha + Risk + Portfolio + Backtest + Execution)
- [x] Orchestrator 编排器 + Agent-as-Tool 模式
- [x] Neo4j 图记忆系统 (策略反思存储/检索)
- [x] ChromaDB RAG 知识库 (Alpha101 论文语义检索)
- [x] 全市场股票池 + 快照预筛选
- [x] 三种交易模式 (回测 / 单次 / 连续)

### Phase 2 — 进行中 🔄
- [ ] 全市场 Alpha 截面排名模型 (替代逐只独立预测)
- [ ] 行业中性化与风险因子暴露控制
- [ ] 多周期回测 (日频 / 周频 / 月频)

### Phase 3 — 规划中 📋
- [ ] Execution Agent 完善 (TWAP / VWAP 算法执行, 订单分片)
- [ ] 记忆系统深度整合 (跨 Agent 经验共享, 策略自动进化)
- [ ] A 股市场接入 (Tushare + Qlib CN 数据)
- [ ] Web Dashboard (实时监控 + 可视化)
- [ ] 回测报告自动生成 (PDF/Markdown)
