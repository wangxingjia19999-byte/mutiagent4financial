# lianghua 多智能体量化项目（基础版）

这个项目先实现了一个可复用的**通用智能体基类**，底层使用：

- LangChain (`ChatOpenAI`)
- LangGraph (`StateGraph`)
- OpenRouter（作为大模型 API 网关）

后续你的其他智能体都可以继承 `BaseAgent`。

## 目录结构

```text
.
├── examples/
│   └── run_quant_agent.py
├── src/
│   └── lianghua_agents/
│       ├── __init__.py
│       ├── base_agent.py
│       ├── config.py
│       └── quant_agent.py
├── .env.example
└── requirements.txt
```

## 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少填入：

- `OPENROUTER_API_KEY`
- `TUSHARE_TOKEN`

3. 运行示例

```bash
PYTHONPATH=src python examples/run_quant_agent.py

# Tushare 拉取 A 股数据后交给智能体分析
PYTHONPATH=src python examples/run_quant_agent_with_tushare.py

# 财报 + 新闻融合分析（自动拉取股票相关新闻）
PYTHONPATH=src python examples/run_financial_news_agent.py

# 总调智能体：融合看图看线 + 财报新闻，给出最终投资判断
PYTHONPATH=src python examples/run_investment_decision_agent.py

# 交互式输入：支持股票代码 + 自定义提示词

支持两种股票代码输入方式：
- 仅数字：如 `000001`（程序会询问是深圳 SZ 还是上海 SH）
- 完整格式：如 `000001.SZ` 或 `600519.SH`

日期默认为：前 30 天 ~ 当前日期（自动计算）

```bash
PYTHONPATH=src python examples/run_interactive_agent.py
```

运行后按提示输入：
1. 选择分析模式（总调/看图看线/财报新闻）
2. 输入股票代码（支持数字或完整格式）
3. 日期范围（默认前30天～今天，可自定义）
4. 可选：输入自定义分析提示词

## Tushare 数据获取

项目内置 `TushareClient`（`src/lianghua_agents/stock_data.py`），可直接获取股票数据：

- `get_stock_basic`：股票基础信息
- `get_daily`：A 股日线行情
- `build_market_snapshot`：将日线数据整理成可喂给 LLM 的市场快照

`QuantResearchAgent` 新增：

- `analyze_stock_with_tushare(ts_code, start_date, end_date, ...)`

调用时会自动：

1) 使用 Tushare 拉取 `ts_code` 的日线数据
2) 生成市场快照
3) 调用量化智能体输出结构化建议

## 财报新闻分析智能体（新增）

已新增 `FinancialNewsAgent`：`src/lianghua_agents/financial_news_agent.py`

- 输入：`ts_code` + 日期区间
- 自动流程：
	1) 拉取财报指标（`fina_indicator`）并生成财报摘要
	2) 自动拉取股票相关新闻（`news` + `major_news`）
	3) 对新闻按股票代码/简称做相关性过滤
	4) 融合财报与事件进行基本面判断

可直接调用：

- Python: `analyze_stock_with_news_reports(ts_code, start_date, end_date, ...)`
- MCP: `analyze_stock_fundamental_news(ts_code, ...)`

如需只取新闻数据，可用：

- MCP: `get_stock_news(ts_code, start_date, end_date, limit)`

## 总调投资决策智能体（新增）

已新增 `InvestmentDecisionAgent`：`src/lianghua_agents/investment_decision_agent.py`

- 融合来源：
	1) `VisualStockAgent`（看图看线/技术面/风控面）
	2) `FinancialNewsAgent`（财报指标+新闻事件）
- 最终输出：
	- 是否可投资（可投资/谨慎观察/暂不投资）
	- 综合评分（0-100）
	- 共识与冲突点
	- 风险清单与执行建议

可直接调用：

- Python: `analyze_stock_for_investment(ts_code, start_date, end_date, ...)`
- MCP: `analyze_stock_investment_decision(ts_code, ...)`

## 看图股票智能体（输入股票代码）

已新增 `VisualStockAgent`：`src/lianghua_agents/visual_stock_agent.py`

- 输入：`ts_code`（如 `000001.SZ`）
- 自动流程（多智能体融合）：
	1) 调用 Tushare 获取日线 + daily_basic
	2) 生成价格/均线/成交量图
	3) 技术面子智能体分析（看图）
	4) 估值面子智能体分析
	5) 风控面子智能体分析
	6) 融合子智能体输出统一信号（看多/中性/看空）

运行示例：

```bash
python examples/run_visual_stock_agent.py
```

## RAG（检索增强）已接入

已新增：`src/lianghua_agents/retriever.py`

- 检索位置：在 `VisualStockAgent` 的 LangGraph 中新增 `retrieve_context` 节点，位于三个子智能体之前。
- 传递方式：检索结果写入状态 `retrieved_context`，技术/估值/风控子智能体共享使用。
- 知识库目录：`knowledge/`（已提供示例文件 `knowledge/stock_analysis_rules.md`）

可调参数：

- Python 调用：`analyze_stock(..., use_rag=True, rag_top_k=4)`
- MCP 调用：`analyze_stock_visual(..., use_rag=true, rag_top_k=4)`

说明：

- 当知识库为空、向量检索失败或未配置好 embedding 时，系统会自动降级，不影响主流程执行。

### 如何做“切分 + 存入”

1. 把知识文档放到 `knowledge/`（支持 `.md`、`.txt`）
2. 运行索引构建：

```bash
python examples/build_rag_index.py
```

3. 系统会自动：

- 对文档做分块切分（默认 `chunk_size=900`, `overlap=120`）
- 计算文件哈希，判断是否需要重建
- 将分块向量写入 Chroma（目录默认 `.chroma/`）

4. 分析时自动检索并注入到多智能体流程。

### 按股票代码过滤知识源

系统会按 `ts_code` 过滤检索结果（例如 `000001.SZ`）：

- 若文档命中对应股票代码，则优先返回该文档分块
- 若未命中，则回退到通用文档（`ALL`）

给知识文档打标的两种方式：

1. 文件名包含股票代码，例如：`knowledge/000001.SZ_strategy.md`
2. 文档头部增加：`symbols: 000001.SZ, 600519.SH`

未标注任何代码的文档会被视为通用文档（`ALL`）。

## MCP 封装（已完成）

已新增 MCP Server：`src/lianghua_agents/mcp_server.py`，提供以下工具：

- `get_stock_basic(exchange, list_status, limit)`
- `get_stock_daily(ts_code, start_date, end_date, limit)`
- `analyze_stock(ts_code, start_date, end_date, limit, strategy)`
- `analyze_stock_visual(ts_code, start_date, end_date, limit)`
- `get_stock_news(ts_code, start_date, end_date, limit)`
- `analyze_stock_fundamental_news(ts_code, start_date, end_date, news_limit, finance_limit, horizon)`
- `analyze_stock_investment_decision(ts_code, start_date, end_date, price_limit, news_limit, finance_limit, use_rag, rag_top_k, horizon, risk_level)`

### 在 conda `wxj` 环境运行

```bash
conda activate wxj
pip install -r requirements.txt
PYTHONPATH=src python -m lianghua_agents.mcp_server
```

### MCP 客户端配置示例

```json
{
	"mcpServers": {
		"lianghua-quant": {
			"command": "conda",
			"args": [
				"run",
				"-n",
				"wxj",
				"python",
				"-m",
				"lianghua_agents.mcp_server"
			],
			"env": {
				"PYTHONPATH": "src",
				"OPENROUTER_API_KEY": "<your_openrouter_key>",
				"TUSHARE_TOKEN": "<your_tushare_token>"
			}
		}
	}
}
```

## 如何扩展新智能体

新建一个类继承 `BaseAgent`，通常只需要重写这些方法：

- `get_system_prompt`：定义角色和输出规范
- `pre_invoke`：调用前改写状态
- `post_invoke`：调用后做格式化/后处理

这样就能保持统一调用方式（`invoke`）和统一图编排（LangGraph）。
