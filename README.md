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
```

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

## MCP 封装（已完成）

已新增 MCP Server：`src/lianghua_agents/mcp_server.py`，提供 3 个工具：

- `get_stock_basic(exchange, list_status, limit)`
- `get_stock_daily(ts_code, start_date, end_date, limit)`
- `analyze_stock(ts_code, start_date, end_date, limit, strategy)`
- `analyze_stock_visual(ts_code, start_date, end_date, limit)`

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
