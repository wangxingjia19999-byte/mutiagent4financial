# 极简使用指南 - 只需输入提示词

你要的功能很简单：**只需输入提示词，其他一切自动处理**。

我已经为你创建了这个功能。现在有两种使用方式：

---

## 方式 1️⃣: 交互窗口（推荐）

最简单的方式 - 启动后，只需要输入你的问题：

```bash
cd /Users/wangxingjia/code/ai_homework/lianghua
PYTHONPATH=src python examples/simple_analyze.py
```

**使用流程**:
```
📊 股票代码 (默认 000001.SZ): [你可以输入其他代码，或直接按 Enter 用默认]

✓ 已选择股票: 000001.SZ

输入你的分析问题 (输入 'exit' 退出)

>>> 这支股票值得投资吗？
[系统自动分析...]

【VISUAL】
... 技术面分析结果 ...

【NEWS】
... 基本面分析结果 ...

【DECISION】
... 综合投资建议 ...

>>> 继续输入下一个问题...
```

**就这么简单！** 不需要管：
- ✅ 日期范围（自动使用过去 30 天）
- ✅ 分析模式（自动使用综合分析）
- ✅ 参数设置（自动使用最优参数）
- ✅ 多个 Agent 协作（自动处理）

只需要输入你的问题，其他都由系统处理。

---

## 方式 2️⃣: 命令行（快速分析）

一行命令直接分析：

```bash
# 基本用法
PYTHONPATH=src python examples/simple_analyze.py "这支股票怎么样？"

# 指定股票代码
PYTHONPATH=src python examples/simple_analyze.py "目标价位是多少？" -s 600519

# 指定其他参数
PYTHONPATH=src python examples/simple_analyze.py "风险大吗？" -s 000001 -r 保守
```

参数说明：
- `prompt`: 你的问题（必须）
- `-s, --stock`: 股票代码（默认：000001.SZ）
- `-h, --horizon`: 投资周期（默认：1-3个月）
- `-r, --risk`: 风险偏好（默认：中等）

---

## 方式 3️⃣: 在代码中使用

如果你想在自己的 Python 代码中使用：

### 最简单的方式

```python
from lianghua_agents.simple_api import analyze_quick

# 只需要一行！
result = analyze_quick("这支股票值得投资吗？")
print(result)
```

### 稍微详细一点

```python
from lianghua_agents.simple_api import analyze

# 分析某支股票
result = analyze(
    prompt="技术面怎么样？",
    ts_code="000001.SZ",  # 可选
)

# 检查结果
if result['status'] == 'success':
    print(result['output'])
else:
    print(f"出错了: {result['errors']}")
```

---

## 完整使用示例

### 场景 1: 快速分析一支股票

```bash
# 打开窗口
$ PYTHONPATH=src python examples/simple_analyze.py

# 输入股票代码（或直接按 Enter）
📊 股票代码 (默认 000001.SZ): 300750

# 输入你的问题
>>> 最近走势如何？
[自动分析...]

>>> 风险有多大？
[自动分析...]

>>> exit
```

### 场景 2: 快速分析多支股票

```bash
# 分析第一支
PYTHONPATH=src python examples/simple_analyze.py "值得买吗？" -s 000001

# 分析第二支
PYTHONPATH=src python examples/simple_analyze.py "值得买吗？" -s 600519

# 分析第三支
PYTHONPATH=src python examples/simple_analyze.py "值得买吗？" -s 300750
```

### 场景 3: 在你的脚本中使用

```python
#!/usr/bin/env python3
from lianghua_agents.simple_api import analyze

stocks = ["000001.SZ", "600519.SH", "300750.SZ"]

for stock in stocks:
    print(f"\n分析 {stock}...")
    result = analyze(f"这支股票的投资价值如何？", ts_code=stock)
    
    if result['status'] == 'success':
        print((result['output']))
    else:
        print(f"分析失败: {result['errors']}")
```

---

## 系统自动处理的事情

不需要你指定，系统自动做：

| 事项 | 系统处理 |
|-----|---------|
| 日期范围 | ✅ 自动使用过去 30 天 |
| 分析模式 | ✅ 自动选择综合分析 |
| Agent 运行 | ✅ 自动运行技术+基本面+决策 |
| Prompt 模板 | ✅ 自动应用统一的 Prompt |
| 数据获取 | ✅ 自动调用 Tushare |
| RAG 知识库 | ✅ 自动启用可选增强 |
| 结果整理 | ✅ 自动格式化输出 |

你只需要：
🎯 **输入提示词**

---

## 交互模式详解

进入交互窗口后的流程：

```
1. 程序启动
   ↓
2. 问你股票代码
   输入: 000001 或 000001.SZ 或直接按 Enter
   ↓
3. 进入问答环节
   >>> 输入你的问题
   [系统自动分析 3-5 秒]
   输出完整分析结果
   ↓
4. 继续输入下一个问题
   └─ 重复第 3 步
   
5. 输入 'exit' 退出
```

---

## 参数说明

### 可选参数

虽然你可以不指定这些，但如果想自定义：

- `horizon` (投资周期)
  - `"1-3个月"` ← default
  - `"1周"`
  - `"3-6个月"`
  - `"1年"`

- `risk_level` (风险偏好)
  - `"保守"` - 低风险
  - `"中等"` ← default
  - `"积极"` - 高风险

- `days_back` (历史数据天数)
  - 默认: 30
  - 可设置: 10, 60, 90 等

使用示例：
```python
result = analyze(
    prompt="风险评估",
    ts_code="000001",
    risk_level="保守",
    days_back=60,  # 使用 60 天数据
)
```

---

## 常见问题

### Q: 可以同时分析多支股票吗？

A: 可以。每个分析是独立的：

```bash
# 连续分析
$ python examples/simple_analyze.py "怎么样？" -s 000001
# 结果输出

$ python examples/simple_analyze.py "怎么样？" -s 600519
# 结果输出
```

或使用交互模式，在同一个窗口中：

```bash
$ python examples/simple_analyze.py
# 输入: 000001
# 输入: 第一个问题
# 输入: 000001
# 输入: 第二个问题
# 输入: exit
```

### Q: 可以保存结果吗？

A: 可以，重定向到文件：

```bash
# 保存命令行分析结果
PYTHONPATH=src python examples/simple_analyze.py "分析" -s 000001 > result.txt

# 或在 Python 中
import json

result = analyze("分析")
with open("result.json", "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

### Q: 如果 API 出错怎么办？

A: 系统会显示 `status: partial` 或 `failed`，并给出错误信息：

```python
result = analyze("问题")

if result['status'] == 'failed':
    print(result['errors'])
```

### Q: 可以改成其他分析模式吗？

A: 可以。系统默认使用综合分析，但你可以通过修改代码改成其他模式。如果需要，可以告诉我。

---

## 推荐使用方式

### 对于快速分析
```bash
PYTHONPATH=src python examples/simple_analyze.py "你的问题"
```

### 对于持续分析
```bash
PYTHONPATH=src python examples/simple_analyze.py
# 然后持续输入问题
```

### 对于程序集成
```python
from lianghua_agents.simple_api import analyze_quick

result = analyze_quick("你的问题")
print(result)
```

---

## 总结

你现在有了你要的功能：

✅ **简单输入窗口** - 只需要提示词  
✅ **自动处理一切** - 日期、参数、模型选择、Agent 协作  
✅ **快速得到结果** - 几秒钟内完整分析  
✅ **灵活使用方式** - CLI、交互、代码集成  

就这么简单! 🎉

```bash
python examples/simple_analyze.py
# 然后就开始输入你的问题吧
```
