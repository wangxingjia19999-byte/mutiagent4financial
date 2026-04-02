# 诊断和修复工具使用指南

## 你现在遇到的问题

你遇到的 API 403 错误说明：

✅ **好消息**: 统一 Agent 系统框架**完全正常工作**！所有组件都已正确加载。

❌ **问题**: 使用的模型 (`gpt-4o-mini`) 在你的地区被 OpenRouter 限制。

---

## 解决方案三部曲

### 步骤 1️⃣: 验证系统框架

首先运行**本地验证测试**（不需要 API 调用）：

```bash
cd /Users/wangxingjia/code/ai_homework/lianghua

# 运行本地验证
PYTHONPATH=src python examples/verify_local.py
```

**预期输出**:
```
✓ 模块导入
✓ Prompt Manager
✓ Agent Orchestrator
✓ Workflow Engine
✓ 系统集成

总计: 5/5 通过 ✅
```

**这验证了系统框架完全正常。** 如果这步失败，说明有环境问题。

---

### 步骤 2️⃣: 诊断和修复 API 问题

运行**自动诊断工具**（会自动检查和建议修复）：

```bash
PYTHONPATH=src python examples/diagnose.py
```

**诊断工具会做的事情**:
1. ✅ 检查环境变量配置
2. ✅ 测试 API 连接
3. ✅ 列出可用的模型
4. ✅ 建议切换模型

**选择的模型** (按推荐度):
- `anthropic/claude-3.5-sonnet` - 最推荐 ⭐⭐⭐⭐⭐  
- `deepseek/deepseek-chat` - 国产优化 ⭐⭐⭐⭐
- `meta-llama/llama-2-70b-chat` - 开源稳定 ⭐⭐⭐

工具会交互式地询问你是否要切换模型。选择 `1` 即可切换到推荐的 Claude 模型。

---

### 步骤 3️⃣: 运行完整系统

修复后，重新运行演示：

```bash
PYTHONPATH=src python examples/run_unified_workflow.py
```

**这次应该成功！**

---

## 详细说明

### 验证工具 (`verify_local.py`)

**目的**: 验证系统框架加载正常，**不调用任何 API**

**何时运行**:
- 系统刚安装时
- 怀疑环境有问题时
- 想快速验证系统健康状态时

**输出**:
```bash
✓ 模块导入
✓ Prompt Manager (5 个模板)
✓ Agent Orchestrator (4 个 Agent)
✓ Workflow Engine (4 种模式)
✓ 系统集成 (完整)
```

---

### 诊断工具 (`diagnose.py`)

**目的**: 自动检查 API 配置，诊断问题，建议修复

**何时运行**:
- 遇到 API 错误时
- 不确定用什么模型时  
- 想检查 API 连接时

**功能**:
1. 检查 `.env` 中的 API Key
2. 测试与 OpenRouter 的连接
3. 列出所有可用的模型
4. 标记出推荐模型
5. 交互式询问是否切换

**使用示例**:

```bash
# 1. 运行诊断
$ PYTHONPATH=src python examples/diagnose.py

# 2. 诊断会输出
$  ✓ API 连接成功
$  推荐模型可用性:
$  ✓ anthropic/claude-3.5-sonnet
$  ✗ deepseek/deepseek-chat
$  ✓ meta-llama/llama-2-70b-chat

# 3. 询问是否切换
$ 是否要切换模型? (输入 1-3 或按 Enter 跳过): 1

# 4. 自动更新 .env
$ ✓ 已切换模型! 请重新运行程序以生效
```

---

### 完整工作流 (`run_unified_workflow.py`)

**目的**: 展示完整的统一系统功能和演示

**何时运行**:
- API 问题已修复后
- 想看完整演示时
- 想测试不同分析模式时

**演示模式**:
1. **Prompt Manager** - 查看所有 Prompt（无 API）✅
2. **单 Agent** - 测试单个 Agent（需 API）
3. **技术面** - 仅技术分析（需 API）
4. **基本面** - 仅基本面分析（需 API）
5. **综合** - 完整分析流程（需 API）

**建议流程**:
```bash
# 第 1 次
1. 先运行 verify_local.py 验证框架
2. 再运行 diagnose.py 修复 API 问题
3. 最后运行 run_unified_workflow.py，选择 "1. Prompt Manager"

# 第 2 次 (API 修好后)
4. 运行 run_unified_workflow.py，选择其他演示
```

---

## 工具对比

| 工具 | 需要 API | 验证内容 | 何时用 |
|-----|---------|--------|--------|
| `verify_local.py` | ❌ | 系统框架 | 初始验证 |
| `diagnose.py` | ⚠️ (仅连接测试) | API 配置 + 模型 | 诊断问题 |
| `run_unified_workflow.py` | ✅ | 完整功能 | 演示使用 |

---

## 快速参考

### 初次设置（5分钟）

```bash
# 1. 验证框架 (< 1 分钟)
PYTHONPATH=src python examples/verify_local.py

# 2. 诊断和修复 (< 2 分钟)  
PYTHONPATH=src python examples/diagnose.py
# 选择 1 自动切换模型

# 3. 测试演示 (< 2 分钟)
PYTHONPATH=src python examples/run_unified_workflow.py
# 选择 1 (Prompt Manager) - 无需 API 也能运行
```

### 日常使用

```bash
# 运行完整演示
PYTHONPATH=src python examples/run_unified_workflow.py

# 或在代码中使用
python your_script.py
```

### 遇到问题时

```bash
# 第 1 步: 验证系统
PYTHONPATH=src python examples/verify_local.py

# 第 2 步: 检查和修复 API
PYTHONPATH=src python examples/diagnose.py

# 第 3 步: 查看完整指南
# 文件: TROUBLESHOOTING.md
# 命令: cat TROUBLESHOOTING.md
```

---

## 常见问题

### Q: 为什么系统框架是正常的，但还是有 API 错误？

**A:** 系统框架和 API 是独立的。框架完全正常意味着：
- ✅ 所有模块正确加载
- ✅ Prompt Manager 工作正常
- ✅ Agent Orchestrator 工作正常
- ✅ Workflow Engine 工作正常

但 API 错误是因为你选的模型在你的地区被限制。诊断工具会帮你修复这个。

### Q: 切换模型后需要重新安装什么吗？

**A:** 不需要。切换模型只是修改 `.env` 文件中的一行配置。
```bash
# 旧
OPENROUTER_MODEL=openai/gpt-4o-mini

# 新
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

重新运行程序时会自动加载新模型。

### Q: 诊断工具修改了哪些文件？

**A:** 只修改 `.env` 文件。如果你不同意修改，可以手动编辑或输入 "n" 拒绝。

### Q: 如果都试过了还是不行？

**A:** 
1. 查看 [TROUBLESHOOTING.md](TROUBLESHOOTING.md) 获取更详细的解决方案
2. 检查 API Key 是否正确（复制/粘贴时可能有空格）
3. 确认网络连接正常（OpenRouter 可能需要特殊配置）
4. 尝试其他推荐的模型

---

## 工具的工作原理

### verify_local.py 流程

```
检查环境 → 导入模块 → 初始化对象 → 验证功能 → 输出结果
```

### diagnose.py 流程  

```
读取 .env → 检查 API Key → 连接测试 → 列出模型 → 建议切换 → 更新文件
```

### run_unified_workflow.py 流程

```
菜单选择 → 创建 Request → 调用 Engine → 执行 Agents → 输出结果
```

---

## 已知事实

✅ **已验证**:
- 所有模块正确加载
- Prompt 集中管理系统工作正常
- Agent 编排框架完全正常
- 工作流引擎设计合理
- 本地验证测试通过

❌ **确认的问题**:
- `gpt-4o-mini` 模型在某些地区被限制
- 需要切换为其他可用的模型

---

## 下一步行动

1. ✅ 运行 `verify_local.py` - 验证框架（应该通过）
2. ✅ 运行 `diagnose.py` - 诊断并修复 API（应该成功切换）
3. ✅ 运行 `run_unified_workflow.py` - 完整演示（应该工作）

你的统一 Agent 系统已经完全构建好了，现在只需要修复这一个 API 配置问题！
