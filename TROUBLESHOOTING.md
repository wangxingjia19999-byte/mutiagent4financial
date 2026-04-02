# API 地域限制问题排查和解决方案

## 问题诊断

你遇到的错误：
```
PermissionDeniedError: Error code: 403 - 
This model is not available in your region.
```

**原因**: OpenRouter 的某些模型（包括 `GPT-4o-mini`）在特定地区被限制。

---

## 解决方案

### 方案 1: 更换为可用的模型（推荐）

#### 🟢 在中国大陆可用的模型：

| 模型 | 提供者 | 推荐度 | 说明 |
|-----|------|------|------|
| `anthropic/claude-3.5-sonnet` | Anthropic | ⭐⭐⭐⭐⭐ | 性能最好，推荐首选 |
| `deepseek/deepseek-chat` | DeepSeek | ⭐⭐⭐⭐ | 本国模型，稳定可靠 |
| `meta-llama/llama-2-70b-chat` | Meta | ⭐⭐⭐ | 开源，可用性好 |
| `mistralai/mistral-large` | Mistral | ⭐⭐⭐ | 性能均衡 |

#### 配置方法：

**方法 A: 通过环境变量（推荐）**

编辑 `.env` 文件：

```bash
# 替换这一行
OPENROUTER_MODEL=openai/gpt-4o-mini

# 改成
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
# 或
OPENROUTER_MODEL=deepseek/deepseek-chat
```

然后重新运行：
```bash
PYTHONPATH=src python examples/run_unified_workflow.py
```

**方法 B: 通过程序代码**

```python
from lianghua_agents.config import AgentSettings
from lianghua_agents.workflow_engine import WorkflowRequest, WorkflowMode, get_workflow_engine

# 创建自定义设置
settings = AgentSettings(
    openrouter_api_key="your_key",
    model="anthropic/claude-3.5-sonnet",  # 换这里
)

# 使用自定义设置
request = WorkflowRequest(
    mode=WorkflowMode.COMPREHENSIVE,
    ts_code="000001.SZ",
    user_prompt="分析这支股票",
)

# 然后正常运行工作流
```

---

### 方案 2: 检查 API 密钥的配置

如果你使用的是付费 OpenRouter 密钥，可能需要检查：

1. **区域白名单设置** - 登录 OpenRouter 后台检查是否限制了中国 IP
2. **配额限制** - 检查是否超过了使用配额
3. **模型许可** - 检查你的 API Key 是否有权限使用该模型

### 方案 3: 使用代理（如果需要）

如果上面的模型仍然不可用，可以配置代理：

```bash
# 在 .env 中添加
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
```

---

## 快速修复步骤

### 第 1 步: 编辑 `.env`

```bash
# 打开 .env 文件
nano .env
```

### 第 2 步: 更新模型

找到这一行：
```
OPENROUTER_MODEL=openai/gpt-4o-mini
```

改成：
```
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

### 第 3 步: 保存并测试

按 `Ctrl+X` 保存，然后运行：

```bash
PYTHONPATH=src python examples/run_unified_workflow.py
```

### 第 4 步: 选择演示 (推荐从简单的开始)

```
选择方案:
1. Prompt Manager 演示     ← 先运行这个（不调用 API）
2. 单 Agent 模式            ← 再运行这个
3. 技术面分析
4. 基本面分析
5. 综合分析
```

---

## 模型性能对比

### Claude 3.5 Sonnet（推荐）
✅ 优点：
- 性能最强（媲美 GPT-4）
- 在中国稳定可用
- 支持较长 context

```bash
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

### DeepSeek（国产）
✅ 优点：
- 本国模型，延迟低
- 理解中文财务术语好
- 成本低

```bash
OPENROUTER_MODEL=deepseek/deepseek-chat
```

### Llama 2（开源）
✅ 优点：
- 完全开放，无地域限制
- 推理速度快

```bash
OPENROUTER_MODEL=meta-llama/llama-2-70b-chat
```

---

## 验证修复

运行这个脚本检查配置是否正确：

```bash
PYTHONPATH=src python -c "
from lianghua_agents.config import AgentSettings
from lianghua_agents.prompt_manager import PromptManager

settings = AgentSettings.from_env()
print(f'✓ API Key: {settings.openrouter_api_key[:20]}...')
print(f'✓ 模型: {settings.model}')
print(f'✓ Base URL: {settings.openrouter_base_url}')
print(f'✓ 可用 Prompt: {PromptManager.list_templates()}')
"
```

---

## 常见问题

### Q: 为什么还是 403？

**A:** 
1. 检查 API 密钥是否正确
2. 检查模型名称是否打对了（大小写敏感）
3. 尝试其他模型
4. 检查网络连接和代理配置

### Q: 如何知道哪些模型在我的地区可用？

**A:** 访问 OpenRouter 官网查看模型列表，或运行：

```bash
PYTHONPATH=src python -c "
import requests
headers = {'Authorization': f'Bearer {你的API_KEY}'}
response = requests.get('https://openrouter.ai/api/v1/models', headers=headers)
models = [m['id'] for m in response.json()['data']]
print('可用模型:')
for m in sorted(models):
    print(f'  - {m}')
" 
```

### Q: 不同模型会影响分析质量吗？

**A:** 会有影响，但框架自身会自动适应。
- Claude 3.5 Sonnet：最佳（推荐）
- DeepSeek：次优（很好）
- Llama 2：可接受（较基础）

---

## 测试修复

完成上述配置后，运行这个测试：

```bash
# 1. 测试 Prompt Manager（无 API 调用）
PYTHONPATH=src python -c "
from lianghua_agents.prompt_manager import PromptManager
prompts = PromptManager.list_templates()
print(f'✓ 加载了 {len(prompts)} 个 Prompt 模板')
"

# 2. 测试单个 Agent（若 API 可用）
PYTHONPATH=src python -c "
from lianghua_agents.agent_orchestrator import get_orchestrator
orchestrator = get_orchestrator()
agents = orchestrator.list_agents()
print(f'✓ 可用 Agent: {list(agents.keys())}')
"

# 3. 运行完整演示
PYTHONPATH=src python examples/run_unified_workflow.py
```

---

## 需要帮助？

如果仍有问题，请提供：

1. 你的 `.env` 中设置的模型名称
2. 命令的完整错误输出
3. 网络环境描述（VPN/代理等）

我会继续帮你排查！
