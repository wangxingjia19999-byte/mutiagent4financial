#!/usr/bin/env python3
"""
快速验证脚本 - 验证极简使用功能是否正常
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def test_simple_api():
    """测试极简 API"""
    print("🧪 测试极简 API\n" + "="*60)
    
    try:
        from lianghua_agents.simple_api import analyze_quick, analyze
        
        print("✓ 导入 analyze_quick 和 analyze")
        
        # 测试函数签名
        print("✓ analyze_quick 签名: analyze_quick(prompt, ts_code='000001.SZ')")
        print("✓ analyze 签名: analyze(prompt, ts_code, horizon, risk_level, days_back)")
        
        return True
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False


def test_simple_cli():
    """测试极简 CLI"""
    print("\n🖥️ 测试极简 CLI\n" + "="*60)
    
    try:
        from pathlib import Path
        cli_path = PROJECT_ROOT / "examples" / "simple_analyze.py"
        
        if cli_path.exists():
            print(f"✓ found CLI script: {cli_path}")
            print("✓ 使用方式:")
            print("  1. 交互模式: python examples/simple_analyze.py")
            print("  2. 快速模式: python examples/simple_analyze.py '你的问题'")
            print("  3. 指定参数: python examples/simple_analyze.py '问题' -s 000001")
            return True
        else:
            print(f"✗ 未找到 CLI 脚本: {cli_path}")
            return False
    
    except Exception as e:
        print(f"✗ 检查失败: {e}")
        return False


def test_multi_agent_system():
    """测试多智能体统一系统"""
    print("\n⚙️  测试多智能体系统\n" + "="*60)
    
    try:
        from lianghua_agents.multi_agent_system import (
            WorkflowRequest,
            WorkflowMode,
            get_multi_agent_system,
        )
        
        print("✓ 导入 MultiAgentSystem")
        
        # 测试创建请求
        request = WorkflowRequest(
            mode=WorkflowMode.COMPREHENSIVE,
            ts_code="000001.SZ",
            user_prompt="测试",
        )
        print("✓ 创建 WorkflowRequest")
        
        # 测试获取引擎
        engine = get_multi_agent_system()
        print("✓ 获取 MultiAgentSystem")
        
        return True
    
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def test_prompt_manager():
    """测试 Prompt Manager"""
    print("\n📝 测试 Prompt Manager\n" + "="*60)
    
    try:
        from lianghua_agents.prompt_manager import PromptManager
        
        templates = PromptManager.list_templates()
        print(f"✓ 可用 Prompt 模板: {len(templates)}")
        
        for name in templates:
            print(f"  • {name}")
        
        return True
    
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║              lianghua 极简功能验证                                    ║
║                                                                       ║
║  检查所有组件是否正常加载                                            ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    tests = [
        ("Prompt Manager", test_prompt_manager),
        ("Multi-Agent System", test_multi_agent_system),
        ("极简 API", test_simple_api),
        ("极简 CLI", test_simple_cli),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} 异常: {e}")
            results.append((test_name, False))
    
    # 总结
    print("\n" + "="*60)
    print("📊 验证结果\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过\n")
    
    if passed == total:
        print("✅ 所有功能正常!\n")
        print("现在可以使用:")
        print("  1. 交互模式: PYTHONPATH=src python examples/simple_analyze.py")
        print("  2. 快速模式: PYTHONPATH=src python examples/simple_analyze.py '你的问题'")
        print("  3. 代码使用: from lianghua_agents.simple_api import analyze_quick")
        print("\n详见: SIMPLE_USAGE_GUIDE.md")
        return 0
    else:
        print("❌ 有些功能异常，请检查上面的错误信息")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
