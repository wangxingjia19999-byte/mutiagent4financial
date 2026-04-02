# 🆘 快速修复指南 - API 403 错误

## 问题
```
PermissionDeniedError: Error code: 403
This model is not available in your region.
```

## 好消息 ✅

你的**统一 Agent 系统完全正常工作**！所有框架都已正确加载。

问题只是：模型 `gpt-4o-mini` 在你的地区被限制了。

## 3 步快速修复（5 分钟）

### 第 1 步: 验证系统框架

```bash
cd /Users/wangxingjia/code/ai_homework/lianghua
PYTHONPATH=src python examples/verify_local.py
```

**预期结果**: ✅ 所有 5 个本地测试通过

### 第 2 步: 自动诊断和修复

```bash
PYTHONPATH=src python examples/diagnose.py
```

**诊断工具会**:
- ✅ 检查你的 API 配置
- ✅ 测试 OpenRouter 连接  
- ✅ 列出可用的模型
- ✅ 提示你选择推荐模型

**当看到这个时**:
```
是否要切换模型? (输入 1-3 或按 Enter 跳过):
```

**输入 `1`** 自动切换到推荐的 Claude 模型（最稳定）

### 第 3 步: 重新运行演示

```bash
PYTHONPATH=src python examples/run_unified_workflow.py
```

**这次应该成功！** 选择 `1` (Prompt Manager) 先测试。

---

## 工具速查表

| 工具 | 命令 | 何时用 |
|-----|------|--------|
| 验证框架 | `python examples/verify_local.py` | 初始验证 |
| 诊断 API | `python examples/diagnose.py` | 修复问题 |
| 完整演示 | `python examples/run_unified_workflow.py` | 功能演示 |

---

## 如果诊断工具不起作用

**手动修复** (编辑 `.env`):

```bash
# 打开 .env
nano .env

# 找到这一行
OPENROUTER_MODEL=openai/gpt-4o-mini

# 改成
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# 保存并退出 (Ctrl+X, Y, Enter)
```

---

## 验证修复成功

```bash
# 运行这个检查是否切换成功
PYTHONPATH=src python -c "
from lianghua_agents.config import AgentSettings
s = AgentSettings.from_env()
print(f'✓ 当前模型: {s.model}')
"

# 应该输出:
# ✓ 当前模型: anthropic/claude-3.5-sonnet
```

---

## 更多帮助

- **完整故障排查**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **诊断工具指南**: [DIAGNOSTIC_TOOLS_GUIDE.md](DIAGNOSTIC_TOOLS_GUIDE.md)
- **系统架构**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **快速开始**: [UNIFIED_SYSTEM_QUICKSTART.md](UNIFIED_SYSTEM_QUICKSTART.md)

---

## 总结

✅ 系统框架: 完全正常  
⚠️ API 模型: 被地区限制  
🔧 修复方式: 切换模型（1 分钟）  
🚀 预期结果: 完整工作  

现在就运行: `python examples/verify_local.py` 开始！
