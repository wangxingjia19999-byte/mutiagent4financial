# 🎯 3 秒快速上手

你想要的功能已经做好了。就这么简单：

---

## 交互窗口 - 推荐 ⭐⭐⭐

```bash
cd /Users/wangxingjia/code/ai_homework/lianghua
PYTHONPATH=src python examples/simple_analyze.py
```

然后：
1. 输入股票代码（可选，按 Enter 用默认 000001.SZ）
2. 输入你的问题
3. **完成！** 系统自动分析

```
>>> 这支股票值得投资吗？
[自动分析...]
【VISUAL】技术面...
【NEWS】基本面...
【DECISION】投资建议...

>>> 继续输入下一个问题
>>> exit
```

---

## 快速命令 - 一行搞定

```bash
PYTHONPATH=src python examples/simple_analyze.py "这支股票怎么样？"
```

---

## 代码中使用

```python
from lianghua_agents.simple_api import analyze_quick

result = analyze_quick("这支股票值得投资吗？")
print(result)
```

---

## 验证功能

```bash
PYTHONPATH=src python examples/test_simple.py
```

---

## 系统自动处理

你只需输入**提示词**，其他一切自动：

- ✅ 日期（过去 30 天）
- ✅ 股票代码（默认 000001）
- ✅ 分析模式（自动综合分析）
- ✅ 所有参数配置
- ✅ 多个 Agent 协作
- ✅ 结果整理

---

## 详细文档

- [SIMPLE_USAGE_GUIDE.md](SIMPLE_USAGE_GUIDE.md) - 完整使用指南
- [README.md](README.md) - 项目概况

---

**就这么简单！** 现在就试试：

```bash
PYTHONPATH=src python examples/simple_analyze.py
```
