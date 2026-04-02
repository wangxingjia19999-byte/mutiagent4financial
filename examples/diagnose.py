#!/usr/bin/env python3
"""
快速诊断和修复脚本 - 检查 API 配置和模型可用性
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dotenv import load_dotenv
load_dotenv()


def check_env_config():
    """检查环境变量配置"""
    print("\n📋 环境变量检查\n" + "="*60)
    
    checks = {
        "OPENROUTER_API_KEY": "OpenRouter API 密钥",
        "TUSHARE_TOKEN": "Tushare Token",
        "OPENROUTER_MODEL": "模型名称（可选，默认 gpt-4o-mini）",
    }
    
    for key, desc in checks.items():
        value = os.getenv(key, "")
        if value:
            # 隐藏敏感信息
            if "KEY" in key or "TOKEN" in key:
                masked = value[:10] + "***" + value[-5:] if len(value) > 15 else "***"
                print(f"✓ {key}: {masked}")
            else:
                print(f"✓ {key}: {value}")
        else:
            print(f"✗ {key}: [未设置]")
    
    return bool(os.getenv("OPENROUTER_API_KEY"))


def check_api_connection():
    """检查 API 连接"""
    print("\n🌐 API 连接检查\n" + "="*60)
    
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("✗ 未找到 OPENROUTER_API_KEY，跳过连接检查")
        return False
    
    try:
        import requests
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5
        )
        
        if response.status_code == 200:
            models = response.json().get("data", [])
            print(f"✓ API 连接成功")
            print(f"  可用模型数: {len(models)}")
            
            # 列出推荐模型
            recommended = [
                "anthropic/claude-3.5-sonnet",
                "deepseek/deepseek-chat",
                "meta-llama/llama-2-70b-chat",
            ]
            
            available = [m["id"] for m in models]
            print(f"\n  推荐模型可用性:")
            for model in recommended:
                status = "✓" if model in available else "✗"
                print(f"  {status} {model}")
            
            return True
        else:
            print(f"✗ API 返回错误 {response.status_code}")
            print(f"  {response.text[:200]}")
            return False
    
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return False


def get_current_model():
    """获取当前配置的模型"""
    try:
        from lianghua_agents.config import AgentSettings
        settings = AgentSettings.from_env()
        return settings.model
    except Exception as e:
        print(f"✗ 无法加载配置: {e}")
        return None


def suggest_model_switch():
    """建议切换模型"""
    print("\n💡 模型切换建议\n" + "="*60)
    
    current = get_current_model()
    print(f"当前模型: {current}\n")
    
    alternatives = [
        ("anthropic/claude-3.5-sonnet", "最推荐 - 性能最强"),
        ("deepseek/deepseek-chat", "国产 - 本土优化"),
        ("meta-llama/llama-2-70b-chat", "开源 - 稳定可靠"),
    ]
    
    print("可切换的模型 (按推荐度排序):\n")
    for i, (model, desc) in enumerate(alternatives, 1):
        print(f"  {i}. {model}")
        print(f"     {desc}\n")
    
    return alternatives


def update_env_file(new_model: str):
    """更新 .env 文件"""
    env_path = PROJECT_ROOT / ".env"
    
    if not env_path.exists():
        print(f"✗ 未找到 .env 文件")
        return False
    
    try:
        content = env_path.read_text()
        
        # 替换或添加 OPENROUTER_MODEL
        if "OPENROUTER_MODEL=" in content:
            lines = content.split('\n')
            new_lines = []
            for line in lines:
                if line.startswith("OPENROUTER_MODEL="):
                    new_lines.append(f"OPENROUTER_MODEL={new_model}")
                else:
                    new_lines.append(line)
            new_content = '\n'.join(new_lines)
        else:
            new_content = content + f"\nOPENROUTER_MODEL={new_model}"
        
        env_path.write_text(new_content)
        print(f"✓ 已更新 .env 文件")
        print(f"  新模型: {new_model}")
        return True
    
    except Exception as e:
        print(f"✗ 更新失败: {e}")
        return False


def test_workflow():
    """测试工作流"""
    print("\n🧪 工作流测试\n" + "="*60)
    
    try:
        from lianghua_agents.prompt_manager import PromptManager
        from lianghua_agents.agent_orchestrator import get_orchestrator
        
        # 测试 Prompt Manager
        prompts = PromptManager.list_templates()
        print(f"✓ Prompt Manager: 已加载 {len(prompts)} 个模板")
        
        # 测试 Orchestrator
        orchestrator = get_orchestrator()
        agents = orchestrator.list_agents()
        print(f"✓ Agent Orchestrator: 已加载 {len(agents)} 个 Agent")
        
        print(f"\n可用的 Agent:")
        for name, desc in agents.items():
            print(f"  • {name}: {desc}")
        
        return True
    
    except Exception as e:
        print(f"✗ 工作流初始化失败: {e}")
        return False


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║         lianghua 快速诊断和修复工具                                   ║
║                                                                       ║
║  这个工具会帮助你：                                                   ║
║  1. 检查环境变量配置                                                 ║
║  2. 测试 API 连接                                                    ║
║  3. 检查模型可用性                                                   ║
║  4. 建议并切换模型                                                   ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    # 1. 检查配置
    if not check_env_config():
        print("\n⚠️  缺少必要的环境变量配置！")
        print("请先编辑 .env 文件配置 OPENROUTER_API_KEY")
        return
    
    # 2. 检查连接
    api_ok = check_api_connection()
    
    # 3. 检查当前模型
    current = get_current_model()
    
    # 4. 建议模型
    alternatives = suggest_model_switch()
    
    # 5. 询问是否切换
    if api_ok:
        print("\n" + "="*60)
        choice = input("是否要切换模型? (输入 1-3 或按 Enter 跳过): ").strip()
        
        if choice in ["1", "2", "3"]:
            model = alternatives[int(choice)-1][0]
            if update_env_file(model):
                print(f"\n✓ 已切换模型! 请重新运行程序以生效")
    
    # 6. 测试工作流
    test_workflow()
    
    print("\n" + "="*60)
    print("✓ 诊断完成\n")
    print("📚 后续步骤:")
    print("  1. 如果切换了模型，请重新运行: python examples/run_unified_workflow.py")
    print("  2. 详细的问题排查: 查看 TROUBLESHOOTING.md")
    print("  3. 有问题? 查看 README.md 或 ARCHITECTURE.md")
    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
