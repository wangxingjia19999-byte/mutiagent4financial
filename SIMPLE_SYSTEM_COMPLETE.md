# 🎉 完成：极简 Agent 系统

你现在拥有了一个**完整的、极简的、强大的 Agent 分析系统**。

---

## 📦 新增内容

### 1️⃣ 极简 API (`simple_api.py`)

```python
# 最简单的用法
from lianghua_agents.simple_api import analyze_quick
result = analyze_quick("这支股票值得投资吗？")
print(result)

# 稍许灵活一点
from lianghua_agents.simple_api import analyze
result = analyze("分析", ts_code="000001.SZ", risk_level="保守")
```

### 2️⃣ 极简 CLI (`simple_analyze.py`)

```bash
# 交互模式 - 推荐
PYTHONPATH=src python examples/simple_analyze.py

# 快速命令
PYTHONPATH=src python examples/simple_analyze.py "你的问题"

# 带参数
PYTHONPATH=src python examples/simple_analyze.py "问题" -s 000001
```

### 3️⃣ 完整示例 (`examples.py`)

```bash
PYTHONPATH=src python examples/examples.py

# 6 个使用示例任选
# 1. 最简单
# 2. 指定股票
# 3. 详细参数
# 4. 检查状态
# 5. 多股票
# 6. 保存结果
```

### 4️⃣ 测试验证 (`test_simple.py`)

```bash
PYTHONPATH=src python examples/test_simple.py

# 验证所有功能是否正常
```

### 5️⃣ 文档

- `QUICK_START_SIMPLE.md` - 最快上手（3 秒）
- `SIMPLE_USAGE_GUIDE.md` - 完整使用指南
- 更新的 `README.md` - 把极简模式放在最前面

---

## 🚀 现在就用

### 最快的方式（推荐）

```bash
cd /Users/wangxingjia/code/ai_homework/lianghua
PYTHONPATH=src python examples/simple_analyze.py

# 然后输入你的问题，系统自动处理一切
```

### 验证功能

```bash
PYTHONPATH=src python examples/test_simple.py
```

### 看示例

```bash
PYTHONPATH=src python examples/examples.py
```

---

## ✨ 功能特点

| 特性 | 描述 |
|-----|------|
| **只需输入提示词** | 无需指定任何参数 |
| **自动处理一切** | 日期、模式、参数、Agent 协作 |
| **三种使用方式** | 交互 / 命令行 / 代码 |
| **快速得到结果** | 几秒钟内完整分析 |
| **灵活扩展** | 需要定制时也支持 |
| **完整的 Agent 系统** | 统一 Prompt + 标准编排 |

---

## 📚 文档导航

根据你的需要选择：

| 你想... | 查看... |
|--------|---------|
| 快速上手 | `QUICK_START_SIMPLE.md` |
| 完整使用 | `SIMPLE_USAGE_GUIDE.md` |
| 代码示例 | `examples.py` |
| 系统架构 | `ARCHITECTURE.md` |

---

## 🎯 到底做了什么

1. **创建了 `simple_api.py`**
   - 提供两个函数：`analyze_quick()` 和 `analyze()`
   - 只需要提示词，其他自动处理

2. **创建了 `simple_analyze.py`**
   - CLI 工具，支持交互和快速模式
   - 无需了解复杂的参数

3. **创建了示例和文档**
   - `examples.py` - 6 个完整的使用示例
   - `test_simple.py` - 功能验证
   - `QUICK_START_SIMPLE.md` - 3 秒上手
   - `SIMPLE_USAGE_GUIDE.md` - 完整指南

4. **建立在统一 Agent 系统之上**
   - PromptManager - 集中管理所有 Prompt
   - AgentOrchestrator - 标准化 Agent 编排
   - WorkflowEngine - 完整的工作流框架

---

## 🔄 使用流程

### CLI 流程

```
启动 CLI
  ↓
输入股票代码（可选）
  ↓
进入问答环节
  ↓
输入提示词
  ↓
系统自动分析（调用所有 Agent）
  ↓
显示结果
  ↓
继续输入下一个问题 / 退出
```

### API 流程

```
调用 analyze_quick(prompt)
  ↓
创建 WorkflowRequest
  ↓
调用 WorkflowEngine
  ↓
执行所有 Agents
  ↓
返回结果
```

---

## 🎁 系统自动处理

你只需提供：
- 📝 提示词（必填）
- 📊 股票代码（可选，默认 000001.SZ）

系统自动做：
- ✅ 计算日期范围（过去 30 天）
- ✅ 选择分析模式（综合分析）
- ✅ 应用 Prompt 模板
- ✅ 运行技术面 Agent
- ✅ 运行基本面 Agent
- ✅ 运行决策综合 Agent
- ✅ 整理输出结果

---

## 💡 使用建议

### 对于快速分析

```bash
PYTHONPATH=src python examples/simple_analyze.py "快速问题" -s 000001
```

### 对于持续交互

```bash
PYTHONPATH=src python examples/simple_analyze.py
# 输入多个问题而无需重启
```

### 对于代码集成

```python
from lianghua_agents.simple_api import analyze_quick
result = analyze_quick("分析")
```

### 对于详细定制

```python
from lianghua_agents.simple_api import analyze
result = analyze(
    prompt="分析",
    ts_code="000001",
    risk_level="保守",
    days_back=60,
)
```

---

## ✅ 验证清单

检查所有功能是否正常：

- [ ] 验证框架: `python examples/test_simple.py`
- [ ] 运行 CLI: `python examples/simple_analyze.py`
- [ ] 查看示例: `python examples/examples.py`
- [ ] 阅读文档: `SIMPLE_USAGE_GUIDE.md`

---

## 最后

你现在拥有一个**完整的、易用的、强大的 Agent 分析系统**。

它结合了：
- 🎯 **极简的用户界面** (只需提示词)
- 🔧 **强大的 Agent 编排** (统一系统)
- 📊 **完整的分析能力** (技术+基本面+决策)

**就这么简单！** 现在就试试：

```bash
PYTHONPATH=src python examples/simple_analyze.py
```

祝你使用愉快！ 🎉
