# Lianghua (量化) — 多 Agent 协作量化投研系统

> 基于 LLM 驱动的多智能体协同框架，覆盖**全市场筛选 → Alpha 挖掘 → 风险控制 → 组合优化 → 回测执行 → 纸交易**的全自动量化投研流水线，支持**美股 (Alpaca) + A 股 (Tushare/EMT)** 双市场，集成 **Neo4j 图记忆**与 **ChromaDB RAG 知识库**，实现策略的持续学习与进化。

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
- **双市场支持** — 美股 (Alpaca) + A 股 (Tushare/东方财富 EMT)，统一抽象层零切换成本

---

## 2. 系统架构

### 2.1 整体架构图

```text
                         ┌──────────────────────────────────────┐
                         │        Market Universe (全市场股票池)   │
                         │  ┌─────────────┐ ┌────────────────┐  │
                         │  │ Alpaca (US) │ │ Tushare (A股)  │  │
                         │  │ 美股全市场    │ │ CSI 300/500    │  │
                         │  └─────────────┘ └────────────────┘  │
                         │   统一 DataProvider 抽象层              │
                         └──────────────┬───────────────────────┘
                                        ▼
                         ┌──────────────────────────────────────┐
                         │       Orchestrator (编排调度层)        │
                         │   ┌──────────────────────────────┐   │
                         │   │  快照预筛：动量 + 成交量 Top-N  │   │
                         │   │  RAG 预查询：检索相关论文知识    │   │
                         │   │  记忆查询：加载历史策略教训       │   │
                         │   │  市场适配：US/CN 自动路由       │   │
                         │   └──────────────────────────────┘   │
                         └──────────┬───────────────────────────┘
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Alpha Agent    │ │  Risk Agent     │ │ Portfolio Agent │
    │  (信号生成)      │ │  (多维风控)      │ │  (组合优化)      │
    │                 │ │                 │ │                 │
    │ • Qlib ML 模型  │ │ • 6维度综合评分  │ │ • 风险调整权重   │
    │ • 158 因子计算  │ │ • 个股风险画像   │ │ • 个股价位上限   │
    │ • IC/IR 评估    │ │ • 市场状态识别   │ │ • 中美订单分派   │
    │ • RAG 因子参考  │ │ • LLM 风险叙事  │ │ • 退出信号生成   │
    └────────┬────────┘ └─────────────────┘ └────────┬────────┘
             │                                       │
             ▼                                       ▼
    ┌─────────────────┐                   ┌─────────────────┐
    │ Backtest Agent  │                   │ Execution Agent │
    │  (回测评估)      │                   │  (订单执行)      │
    │                 │                   │                 │
    │ • Qlib 回测引擎 │                   │ • Alpaca 纸交易  │
    │ • 滚动周验证    │                   │ • CNPaperBroker  │
    │ • 绩效归因分析  │                   │ • EMT 极速柜台   │
    │ • 可视化报告    │                   │ • T+1 / 涨跌停   │
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

### 2.2 市场抽象层设计

系统通过 `MarketConfig` + `DataProvider` + `Broker` + `MarketCalendar` 四层抽象，实现美股和 A 股的统一编排：

```text
                    ┌─────────────────────────────┐
                    │     Orchestrator             │
                    │  (市场无关的编排逻辑)          │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
    │ MarketConfig│  │ DataProvider│  │    Broker       │
    │             │  │             │  │                 │
    │ US: T+0,$   │  │ AlpacaProv. │  │ AlpacaBroker    │
    │    1 share  │  │ TushareProv.│  │ CNPaperBroker   │
    │ CN: T+1,¥   │  │ EMQProvider │  │ EMTBroker       │
    │    100股/手 │  │ MockProvider│  │ (极速柜台)       │
    └─────────────┘  └─────────────┘  └─────────────────┘
              │                │                │
              └────────────────┼────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   MarketCalendar    │
                    │ US: 9:30-16:00 ET   │
                    │ CN: 9:30-15:00 CST  │
                    │   + 节假日日历       │
                    └─────────────────────┘
```

### 2.3 数据流时序

```text
用户命令
  │
  ▼
[1] Market Universe ──► 拉取全市场股票 (Alpaca / Tushare)
  │
  ▼
[2] Orchestrator ──► 快照预筛 (动量+成交量) → RAG 查询 → 记忆查询
  │
  ├─► [3] Alpha Agent ──► Qlib ML 预测 → 因子信号输出
  ├─► [4] Risk Agent  ──► 6维度评分 → 个股风险画像 → 仓位上限 → LLM风险叙事
  ├─► [5] Portfolio   ──► 风险调整权重 → 个股价位上限 → 订单生成 (US/CN)
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

负责拉取全市场可交易标的，是整个流水线的数据入口。

**美股 (AlpacaProvider)**

| 特性 | 说明 |
|------|------|
| 覆盖范围 | NYSE、NASDAQ 全市场活跃股票 |
| 筛选逻辑 | 剔除 OTC、仙股（<$2）、日均成交量 < 10 万股 |
| 分级范围 | `nasdaq100`(≈100只) / `sp500`(≈500只) / `liquid`(≈2000只) / `all` |
| 缓存策略 | 24 小时磁盘缓存，减少 API 调用 |

**A 股 (TushareProvider + FullMarketScreener)**

| 特性 | 说明 |
|------|------|
| 覆盖范围 | 沪深两市 5000+ 只股票 |
| 分级范围 | `csi300`(≈300只) / `csi500`(≈500只) / `liquid_cn`(≈2000只) / `all_cn`(全市场) |
| 筛选逻辑 | 剔除 ST/*ST/退市/暂停上市/新股；价格 ¥2–¥3000；日成交量 > 10万股 |
| 多因子精选 | FullMarketScreener: 动量 + 流动性 + 换手率 + 低波偏好 → Top 200–500 |
| 数据源 | Tushare (历史) / EMQProvider (实时 L1/L2) → Mock 兜底 |

### 3.2 Orchestrator — 多 Agent 编排器

系统的中枢调度层，负责串联各 Agent 的执行顺序与数据传递。

**两阶段预筛选（实时模式）**
1. **Snapshot 快照预筛** — 按动量绝对值 × log(成交量) 打分，选出 Top 200 候选（US）/ 或 FullMarketScreener 多因子精选（CN）
2. **ML 精选** — Alpha Agent 对候选股票计算 RSI / MACD / Bollinger 等 158 个因子，模型预测排序

**市场自动路由**
- 指定 `--market cn` 或 `--universe csi300/csi500/liquid_cn/all_cn` → 自动切换 A 股模式
- 自动选择对应货币 (¥)、手数规则 (100 股/手)、T+1 结算

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

### 3.4 Risk Agent — 多维风控系统

**6 维度加权综合评分**，输出组合级别 + 个股级别风险画像。

| 风险维度 | 指标 | 权重 | 说明 |
|----------|------|------|------|
| 波动率 | Annualized Volatility | 20% | 年化波动率 + 短期波动率 |
| 尾部风险 | VaR (95%) + CVaR | 20% | 历史 VaR + 条件尾部期望 |
| 回撤风险 | Max Drawdown | 20% | 组合历史最大回撤 |
| 相关性 | 平均成对相关性 | 15% | 分散化效果评估 |
| 集中度 | HHI 指数 | 10% | 组合持仓集中度 |
| 波动突变 | Vol Ratio (短期/长期) | 15% | 识别波动率异常放大 |

**个股风险画像**（每只股票独立计算）
- 个股波动率 / 最大回撤 / Beta / VaR / Sharpe / Sortino / 流动性
- 个股风险评分 → 风险等级 → **仓位上限 (position_cap)**

| 市场状态 | 低风险个股 | 中风险 | 高风险 | 极高风险 |
|----------|-----------|--------|--------|---------|
| LOW 大盘风险 | 18% cap | 12% cap | 8% cap | 5% cap |
| MODERATE | 10% cap | 7% cap | 5% cap | 3% cap |
| HIGH 大盘风险 | 6% cap | 4% cap | 3% cap | 2% cap |

**市场状态识别** — 5 种状态：`trending_bull`, `trending_bear`, `high_volatility`, `ranging`, `weak_trend`

**LLM 风险叙事** — LLM 可用时自动生成中文风控建议；不可用时回退规则叙事

### 3.5 Portfolio Agent — 组合优化

将 Alpha 信号 + 多维风险信号转化为可执行的投资组合。

- **风险调整权重** — Alpha 得分 × 风险倒数加权（安全股更高权重，高风险股受限）
- **个股价位上限** — 严格遵循 Risk Agent 输出的 position_cap
- **智能重分配** — Cap 导致欠配时，自动放大权重直至目标配置
- **中美订单分派** — US: 碎股市场单 → `generate_orders()` / CN: 整手限价单 → `generate_orders_cn()`
- **退出信号** — 识别持仓中应卖出的标的

### 3.6 Backtest Agent — 回测引擎

基于 Qlib 回测框架的完整历史模拟。

- **Standard 回测** — 固定训练/测试区间
- **Rolling Weekly 回测** — 每周滚动重训，避免前视偏差
- **绩效报告** — 总收益、Sharpe、最大回撤、波动率、风险等级、市场状态
- **Long-Short 回测** — 多空组合模拟

### 3.7 Execution Agent — 交易执行

对接交易 API 的订单执行层，支持多市场。

**美股 (AlpacaBroker)**
- Alpaca Paper Trading API
- 市价单 / 限价单 / 止损单
- T+0 结算

**A 股模拟 (CNPaperBroker)**
- 内存模拟纸交易，完整实现 A 股规则：
  - T+1 结算（今日买入次日可卖）
  - 涨跌停限制（主板 ±10% / 创业板 ±20% / 科创板 ±20% / 北交所 ±30%）
  - 整手交易（100 股/手）
  - FIFO 成本核算 → 已实现盈亏
  - 印花税（卖出 0.05%）+ 佣金 + 过户费

**A 股实盘 (EMTBroker)**
- 对接东方财富 EMT 极速柜台（CTP 兼容协议）
- 支持普通账户 / 信用账户 / 期权账户
- TCP 直连 61.152.230.41:19088

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
| Alpaca Markets | 免费账号 | 美股纸交易 + 全市场数据 |
| Tushare | 免费/付费 Token | A 股数据 |
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

| 变量 | 说明 | 市场 | 必须 |
|------|------|------|------|
| `ALPACA_API_KEY` | Alpaca API Key | US | ✅ |
| `ALPACA_SECRET_KEY` | Alpaca Secret Key | US | ✅ |
| `POE_API_KEY` | Poe API 密钥 (LLM) | 通用 | ✅ |
| `OPENAI_API_KEY` | OpenAI API Key | 通用 | - |
| `TUSHARE_TOKEN` | Tushare A 股数据 Token | CN | A 股需要 |
| `NEO4J_URI` | Neo4j 连接地址 | 通用 | 可选 |
| `NEO4J_USER` | Neo4j 用户名 | 通用 | 可选 |
| `NEO4J_PASSWORD` | Neo4j 密码 | 通用 | 可选 |

### 4.4 运行

```bash
# ═══════════════════════════════════════════════════════════
#  美股 (US) — Alpaca Markets
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  A 股 (CN) — Tushare / 东方财富 EMT
# ═══════════════════════════════════════════════════════════

# 回测 CSI 300 成分股
python run_paper_trading.py --market cn --universe csi300 --mode backtest --start 2024-01-01 --end 2024-03-01

# 回测 CSI 500 成分股
python run_paper_trading.py --market cn --universe csi500 --mode backtest --start 2024-01-01 --end 2024-06-01

# 全 A 股流动性筛选 + 回测
python run_paper_trading.py --market cn --universe liquid_cn --mode backtest --start 2024-01-01 --end 2024-03-01

# 手工指定 A 股
python run_paper_trading.py --market cn --symbol 000001.SZ,600519.SH --mode backtest --start 2024-01-01 --end 2024-03-01

# A 股纸交易（模拟 T+1 + 涨跌停）
python run_paper_trading.py --market cn --universe csi300 --mode once

# A 股连续自动交易
python run_paper_trading.py --market cn --universe liquid_cn --mode continuous --interval 300

# A 股实盘 (EMT 极速柜台)
python run_paper_trading.py --market cn --broker emt --universe csi300 --mode once


# ═══════════════════════════════════════════════════════════
#  子模块 Demo
# ═══════════════════════════════════════════════════════════

python agent_pools/alpha_agent_pool/alpha_research_agent.py  # Alpha 因子研究
python agent_pools/risk_agent_demo/risk_signal_agent.py        # 多维风控 Demo
```

### 4.5 `--universe` 参数

**美股 (--market us)**

| 值 | 股票数量 | 筛选条件 |
|------|------|------|
| `nasdaq100` | ≈100 | 快照打分 Top 100 |
| `sp500` | ≈500 | 快照打分 Top 500 |
| `liquid` | ≈2000 | 价格 > $2，日均成交 > 10 万股 |
| `all` | 全部 | 仅保留 NYSE/NASDAQ 主要交易所标的 |

**A 股 (--market cn)**

| 值 | 股票数量 | 筛选条件 |
|------|------|------|
| `csi300` | ≈300 | CSI 300 成分股 |
| `csi500` | ≈500 | CSI 500 成分股 |
| `liquid_cn` | ≈2000 | 价格 ¥2–¥3000，成交量 > 10 万股，剔除 ST/新股 |
| `all_cn` | ≈5000 | 全市场（自动多因子精选至 Top 200–500） |

### 4.6 A 股特有 CLI 参数

| 参数 | 说明 |
|------|------|
| `--market cn` | 切换 A 股市场模式（CNY / T+1 / 100股/手） |
| `--broker emt` | 使用 EMT 极速柜台（实盘），默认 paper（模拟） |
| `--no-filter` | 关闭全市场预筛选（all_cn 模式下默认开启多因子精选） |

---

## 5. A 股实现详解

### 5.1 市场配置 (`market/config.py`)

```python
CN_MARKET = MarketConfig(
    code="cn", currency="CNY", currency_symbol="¥",
    lot_size=100,              # 100 股/手
    price_limit_pct=0.10,      # 主板 ±10%
    settlement="T+1",          # 当日买入次日可卖
    timezone="Asia/Shanghai",
    trading_days_per_year=244, # A 股年均 244 个交易日
    min_commission=5.0,        # 最低 ¥5/笔
    stamp_duty_sell=0.0005,    # 卖出印花税 0.05%
)
```

### 5.2 数据提供层 (`data/providers/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| **TushareProvider** | `tushare_provider.py` | A 股历史日线 OHLCV + 实时价格 + 股票池拉取 (stock_basic) |
| **EMQProvider** | `emq_provider.py` | 东方财富 EMQ 极速行情（CTP 协议），Level-1/Level-2 实时行情 |
| **FullMarketScreener** | `full_market_screener.py` | 5000+ 全市场多因子筛选：流动性 + 动量 + 换手率 + 低波 → Top 200–500 |
| **MockProvider** | `mock_provider.py` | Mock 数据兜底，Tushare 不可用时自动降级 |

**Tushare 股票池分级**

```text
沪深全市场 (~5400只)
  │
  ├─  ST/*ST/退市/暂停 → 剔除 (~300只)
  │
  ├─  liquid_cn 筛选 (价格/成交量/市值) → ~2000只
  │
  ├─  csi300 → 沪深300成分股 → ~300只
  ├─  csi500 → 中证500成分股 → ~500只
  │
  └─  FullMarketScreener 多因子精选 → Top 200–500 只候选
```

### 5.3 交易执行层 (`broker/`)

| 组件 | 文件 | 功能 |
|------|------|------|
| **CNPaperBroker** | `cn_paper_broker.py` | 内存模拟 A 股纸交易 |
| **EMTBroker** | `emt_broker.py` | 东方财富 EMT 极速柜台实盘交易 |

**CNPaperBroker 核心规则**
- **T+1 结算** — 当日买入的股票锁仓至次日；卖出时自动检查可卖数量
- **涨跌停限制** — 按股票代码自动识别板块（主板/创业板/科创板/北交所），应用对应涨跌幅限制
- **整手交易** — 100 股/手，订单数量自动取整
- **FIFO 成本核算** — 按买入批次 (Lot) 先进先出，精确计算已实现盈亏
- **费用模拟** — 卖出印花税 (0.05%) + 佣金 (最低 ¥5) + 过户费

**EMTBroker** — 东方财富极速柜台
- CTP 兼容协议 (FTD 二进制协议)
- 普通账户 / 信用账户 (两融) / 期权账户
- TCP 直连：61.152.230.41:19088 (交易) / 61.152.230.41:29088 (行情)

### 5.4 交易日历 (`market/cn_calendar.py`)

- 交易时间 (CST/UTC+8)：上午 9:30–11:30，下午 13:00–15:00
- 午间休市：11:30–13:00
- 节假日日历：`market/cn_holidays.csv`
- 自动判断开盘/休市状态（含盘前/午休/盘后状态描述）

### 5.5 订单生成差异

| 特性 | 美股 `generate_orders()` | A 股 `generate_orders_cn()` |
|------|--------------------------|---------------------------|
| 手数 | 1 股 (碎股) | 100 股/手 (整手取整) |
| 单类型 | 市价单 / 限价单 | 限价单 (推荐) |
| 最低交易额 | $100 | ¥10,000 |
| 货币符号 | $ | ¥ |

---

## 6. 技术栈总览

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **Agent 框架** | OpenAI SDK / LangChain | LLM 驱动的 Agent 推理与工具调用 |
| **大语言模型** | GPT-4o / Claude (Poe 代理) | Agent 的"大脑" |
| **量化框架** | Qlib (Microsoft) | 158 标准化因子 + ML 模型 + 回测引擎 |
| **美股数据** | Alpaca Markets API | 全市场实时/历史数据 |
| **美股交易** | Alpaca Trading API | 纸交易 (模拟) / 实盘 |
| **A 股数据** | Tushare / 东方财富 EMQ | 历史日线 + L1/L2 实时行情 |
| **A 股交易** | CNPaperBroker / EMT 极速柜台 | 模拟纸交易 / CTP 实盘 |
| **图数据库** | Neo4j | Agent 记忆图谱存储 |
| **向量数据库** | ChromaDB | RAG 知识库语义检索 |
| **通信协议** | MCP / A2A | Agent 间标准化通信 |
| **数据缓存** | Disk Cache (24h) | 减少 API 重复调用 |

---

## 7. 项目亮点

### 7.1 技术创新

| 亮点 | 说明 |
|------|------|
| **LLM + 量化融合** | 不是简单的 LLM 包装，而是让 LLM 真正参与因子设计、策略决策 |
| **Agent-as-Tool** | 每个 Agent 既可作为独立工具运行，也可被编排器作为子工具调度 |
| **图记忆系统** | 策略经验以知识图谱形式沉淀，跨任务复用 |
| **RAG 增强** | Agent 决策前自动检索 Alpha101 学术论文，让"理论指导实践" |
| **滚动周验证** | 严格的 Walk-Forward 回测，避免前视偏差 |
| **全市场覆盖** | 不局限于几只股票，真正实现全市场选股 |
| **双市场统一抽象** | 一套编排逻辑驱动美股 + A 股，市场差异完全由底层抽象处理 |

### 7.2 工程亮点

| 亮点 | 说明 |
|------|------|
| **统一入口** | `run_paper_trading.py` 一个命令覆盖所有模式和市场 |
| **市场自动路由** | 指定 `--universe csi300` 自动切换 A 股，无需手动配置 |
| **优雅降级** | Neo4j/Qlib/Tushare 不可用时自动切换 Mock 模式，不影响核心流程 |
| **模块解耦** | 每个 Agent 独立可测试，通过 Orchestrator 松耦合 |
| **实时快筛** | 美股 2000+ 秒级预筛选 / A 股 5000+ 多因子精选 |
| **RAG 自动构建** | 首次使用时自动从 PDF 构建向量索引，零配置 |

---

## 8. 目录结构

```text
lianghua/
├── run_paper_trading.py              # 主入口 (回测/实时/连续交易，US+CN)
│
├── orchestrator_demo/                # 多 Agent 编排调度层
│   └── orchestrator.py               # Orchestrator 中枢调度器
│
├── market/                           # 市场抽象层 (NEW)
│   ├── config.py                     #   MarketConfig (US/CN 预定义)
│   ├── calendar_base.py              #   日历基类
│   ├── us_calendar.py                #   美股交易日历
│   ├── cn_calendar.py                #   A 股交易日历 (含节假日)
│   └── cn_holidays.csv               #   A 股节假日期表
│
├── data/providers/                   # 数据提供层 (NEW)
│   ├── base.py                       #   DataProvider 抽象基类
│   ├── alpaca_provider.py            #   美股 Alpaca 实现
│   ├── tushare_provider.py           #   A 股 Tushare 实现
│   ├── emq_provider.py               #   东方财富 EMQ L1/L2 实时行情
│   ├── full_market_screener.py       #   A 股全市场多因子筛选器
│   └── mock_provider.py              #   Mock 数据兜底
│
├── broker/                           # 交易执行层 (NEW)
│   ├── base.py                       #   Broker 抽象基类
│   ├── alpaca_broker.py              #   美股 Alpaca 实现
│   ├── cn_paper_broker.py            #   A 股纸交易 (T+1/涨跌停/整手/FIFO)
│   └── emt_broker.py                 #   EMT 极速柜台 (CTP 协议)
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
│   ├── risk_agent_demo/              # 多维风控 Agent
│   │   └── risk_signal_agent.py      #   6维度评分 + 个股画像 + LLM 叙事
│   ├── portfolio_agent_demo/         # 组合优化 Agent
│   │   └── portfolio_agent.py        #   风险调整权重 + 中美订单分派
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
│   └── cache/                        #   市场股票池缓存
├── trade_journals/                   # 交易日志
├── requirements.txt
└── pyproject.toml
```

---

## 9. 开发路线图

### Phase 1 — 已完成 ✅
- [x] 多 Agent 协作框架 (Alpha + Risk + Portfolio + Backtest + Execution)
- [x] Orchestrator 编排器 + Agent-as-Tool 模式
- [x] Neo4j 图记忆系统 (策略反思存储/检索)
- [x] ChromaDB RAG 知识库 (Alpha101 论文语义检索)
- [x] 全市场股票池 + 快照预筛选
- [x] 三种交易模式 (回测 / 单次 / 连续)

### Phase 2 — 已完成 ✅
- [x] **A 股市场完整接入** (Tushare + EMT + CNPaperBroker)
- [x] **市场抽象层设计** (MarketConfig + DataProvider + Broker + Calendar)
- [x] **Risk Agent 多维升级** (6 维度评分 + 个股风险画像 + 仓位上限 + 市场状态识别 + LLM 风险叙事)
- [x] **Portfolio Agent 风险调整** (风险倒数加权 + 个股价位上限 + 智能重分配)
- [x] A 股全市场多因子筛选器 (FullMarketScreener)
- [x] A 股纸交易模拟 (T+1 / 涨跌停 / 整手 / FIFO)
- [x] EMT 极速柜台接入 (CTP 协议)

### Phase 3 — 规划中 📋
- [ ] 全市场 Alpha 截面排名模型 (替代逐只独立预测)
- [ ] 行业中性化与风险因子暴露控制
- [ ] Execution Agent 完善 (TWAP / VWAP 算法执行)
- [ ] 记忆系统深度整合 (跨 Agent 经验共享, 策略自动进化)
- [ ] Web Dashboard (实时监控 + 可视化)
- [ ] 回测报告自动生成 (PDF/Markdown)
- [ ] 港股市场接入
