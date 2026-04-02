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

### 推荐方式：CLI 模式

#### 对话模式（新增）- 直接输入提示词交互
```bash
# 进入对话模式，连续输入多个分析需求
PYTHONPATH=src python examples/cli.py chat

# 也可以指定股票代码，跳过首次询问
PYTHONPATH=src python examples/cli.py chat -s 000001
```

对话模式说明：
- 输入任意文本作为分析提示词
- 输入 `help` 显示命令
- 输入 `exit` 退出

#### 参数分析模式
```bash
# 交互模式（询问所有参数）
PYTHONPATH=src python examples/cli.py analyze -i

# 参数模式（指定参数）
PYTHONPATH=src python examples/cli.py analyze -s 000001 -m decision

# 总调投资决策（默认模式）
PYTHONPATH=src python examples/cli.py analyze -s 000001

# 看图看线分析
PYTHONPATH=src python examples/cli.py analyze -s 000001 -m technical

# 财报新闻分析（可选日期）
PYTHONPATH=src python examples/cli.py analyze -s 000001 -m fundamental --start-date 20260301 --end-date 20260331

# 模拟盘执行（分析 + 自动按信号下单）
PYTHONPATH=src python examples/cli.py paper -s 000001 --risk-level 中等
```

## ⚡ 最快开始（极简模式）

**你要的就是这个！只需输入提示词，其他一切自动处理。**

### 方式 1: 交互窗口（最简单）

```bash
PYTHONPATH=src python examples/simple_analyze.py
```

然后：
1. 输入股票代码（或按 Enter 用默认）
2. 输入你的问题
3. 系统自动分析并显示结果

```
>>> 这支股票值得投资吗？
[自动分析...]
【VISUAL】技术面分析...
【NEWS】基本面分析...
【DECISION】投资建议...
```

### 方式 2: 快速命令

```bash
PYTHONPATH=src python examples/simple_analyze.py "这支股票怎么样？" -s 000001
```

### 方式 3: 代码

```python
from lianghua_agents.simple_api import analyze_quick
result = analyze_quick("这支股票值得投资吗？")
print(result)
```

✨ **系统自动处理**:
- ✅ 日期范围（过去 30 天）
- ✅ 分析模式（综合分析）
- ✅ 所有参数设置
- ✅ 多 Agent 协作

详见: [SIMPLE_USAGE_GUIDE.md](SIMPLE_USAGE_GUIDE.md)

---

## ✨ 新增：统一 Agent 系统（用于高级定制）

lianghua 现在支持一个**完整的统一 Agent 管理系统**，解决了之前 Agent 各自为政的问题！

### 核心特性

- ✅ **集中 Prompt 管理** - 所有 Agent 的提示词在一个地方管理
- ✅ **统一工作流引擎** - 支持单 Agent / 技术面 / 基本面 / 综合分析等多种模式
- ✅ **标准化 Agent 编排** - 清晰的多 Agent 协作框架
- ✅ **完整的输入/输出规范** - 统一的数据格式

### 快速开始

#### 第 1 步: 验证系统框架 ✅

```bash
# 运行本地验证（不需要 API 调用）
PYTHONPATH=src python examples/verify_local.py

# 应该看到所有测试都通过 ✓
```

#### 第 2 步: 诊断/修复 API 问题 (如果需要)

```bash
# 如果遇到 API 403 错误，运行诊断工具
PYTHONPATH=src python examples/diagnose.py

# 工具会自动检查和建议切换模型
```

#### 第 3 步: 运行演示程序 🚀

```bash
# 交互式演示，查看 Prompt Manager、各种分析模式
PYTHONPATH=src python examples/run_unified_workflow.py

# 推荐先选择: 1. Prompt Manager 演示（无需 API）
```

#### 第 4 步: 在代码中使用

```python
from lianghua_agents.multi_agent_system import (
    WorkflowRequest,
    WorkflowMode,
	get_multi_agent_system,
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

# 运行并获取结果
result = get_multi_agent_system().run(request)
print(result.results)
```

### 支持的分析模式

| 模式 | 说明 | Agent 组合 |
|-----|------|-----------|
| **SINGLE** | 单 Agent 分析 | 指定的单个 Agent |
| **TECHNICAL** | 技术面分析 | VisualStockAgent |
| **FUNDAMENTAL** | 基本面分析 | FinancialNewsAgent |
| **COMPREHENSIVE** | 完整分析 | Visual + News + Decision |

### 查看所有 Prompt

```python
from lianghua_agents.prompt_manager import PromptManager

# 列出所有可用的 Agent Prompt
for name in PromptManager.list_templates():
    print(name)

# 查看特定 Agent 的 Prompt
prompt = PromptManager.render_system_prompt("investment_decision_agent")
print(prompt)
```

### 🆘 遇到 API 错误？

**错误信息**: `PermissionDeniedError: model not available in your region`

**解决方案**: 

```bash
# 自动诊断和修复
PYTHONPATH=src python examples/diagnose.py

# 或查看完整指南
# 文件: TROUBLESHOOTING.md
```

### 详细文档

- **快速开始**: [UNIFIED_SYSTEM_QUICKSTART.md](UNIFIED_SYSTEM_QUICKSTART.md)
- **完整架构**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **故障排查**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

### 旧模式（仍然可用）

```bash
# Tushare 拉取 A 股数据后交给智能体分析
PYTHONPATH=src python examples/run_quant_agent_with_tushare.py

# 财报 + 新闻融合分析（自动拉取股票相关新闻）
PYTHONPATH=src python examples/run_financial_news_agent.py

# 总调智能体：融合看图看线 + 财报新闻，给出最终投资判断
PYTHONPATH=src python examples/run_investment_decision_agent.py

# 模拟盘示例：总调决策 + 本地账户执行
PYTHONPATH=src python examples/run_paper_trading_agent.py

# 简单交互式输入：支持股票代码 + 自定义提示词
PYTHONPATH=src python examples/run_interactive_agent.py
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

## CLI 命令行工具（推荐）

已新增专业 CLI 封装：`src/lianghua_agents/cli.py`，使用 `click` 和 `rich` 实现。

### CLI 参数说明

- `-s, --stock-code`：股票代码（如 `000001` 或 `000001.SZ`）
- `-m, --mode`：分析模式
  - `decision`：总调投资决策（融合技术+财报+新闻）【默认】
  - `technical`：看图看线（技术面分析）
  - `fundamental`：财报新闻（基本面+事件）
- `--start-date`：开始日期（YYYYMMDD，默认30天前）
- `--end-date`：结束日期（YYYYMMDD，默认今天）
- `-p, --custom-prompt`：自定义分析提示词
- `-i, --interactive`：交互模式

### 模拟盘（Paper Trading）

已新增：`src/lianghua_agents/paper_trading.py`

功能：

- 本地账户持久化（默认 `.paper_account.json`）
- 解析 `InvestmentDecisionAgent` 输出（可投资/谨慎观察/暂不投资）转为 BUY/HOLD/SELL
- 风险偏好驱动目标仓位（保守/中等/积极）
- 简单止损（默认回撤 8% 触发清仓）

CLI 用法：

```bash
PYTHONPATH=src python examples/cli.py paper -s 000001 --risk-level 中等
```

可选参数：

- `--state-path`：账户状态文件路径（默认 `.paper_account.json`）
- `--initial-cash`：首次初始化资金（默认 1000000）
- `-p, --custom-prompt`：附加给总调智能体的提示词

### CLI 输出特性

- 彩色美化输出（使用 Rich 库）
- 进度指示（分析过程显示加载动画）
- 结果面板（结构化展示分析结论）

---

## 旧交互模式（仍然可用）

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
