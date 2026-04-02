#!/usr/bin/env python3
"""
本地验证脚本 - 不需要 API 调用，验证系统框架是否正常
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def test_imports():
    """测试所有模块导入"""
    print("📦 测试模块导入...\n")
    
    modules = [
        ("prompt_manager", "PromptManager"),
        ("agent_orchestrator", "AgentOrchestrator"),
        ("multi_agent_system", "MultiAgentSystem, WorkflowMode"),
        ("base_agent", "BaseAgent"),
        ("config", "AgentSettings"),
    ]
    
    for module_name, classes in modules:
        try:
            module = __import__(f"lianghua_agents.{module_name}", fromlist=classes.split(", "))
            print(f"✓ {module_name}: 导入成功")
        except Exception as e:
            print(f"✗ {module_name}: {e}")
            return False
    
    return True


def test_prompt_manager():
    """测试 Prompt Manager"""
    print("\n📝 测试 Prompt Manager...\n")
    
    from lianghua_agents.prompt_manager import PromptManager
    
    # 测试列出所有模板
    templates = PromptManager.list_templates()
    print(f"✓ 可用模板数: {len(templates)}")
    for name in templates:
        print(f"  • {name}")
    
    # 测试获取模板
    print(f"\n✓ 获取特定模板:")
    for name in ["visual_stock_agent", "investment_decision_agent"]:
        template = PromptManager.get_template(name)
        print(f"  • {template.name} (v{template.version})")
    
    # 测试渲染
    print(f"\n✓ 测试 Prompt 渲染:")
    prompt = PromptManager.render_system_prompt(
        "investment_decision_agent",
        horizon="1-3个月",
        risk_level="中等",
    )
    print(f"  生成的 prompt 长度: {len(prompt)} 字符")
    
    return True


def test_agent_orchestrator():
    """测试 Agent Orchestrator"""
    print("\n🎭 测试 Agent Orchestrator...\n")
    
    from lianghua_agents.agent_orchestrator import get_orchestrator, AgentOrchestrator
    
    # 测试获取全局实例
    orchestrator = get_orchestrator()
    print(f"✓ 获取全局 Orchestrator 实例")
    
    # 测试列出可用 Agent
    agents = AgentOrchestrator.list_agents()
    print(f"\n✓ 可用 Agent ({len(agents)} 个):")
    for name, desc in agents.items():
        print(f"  • {name}: {desc}")
    
    # 测试获取 Agent 实例
    print(f"\n✓ 获取 Agent 实例:")
    for agent_name in ["visual", "news", "decision"]:
        agent = orchestrator.get_agent(agent_name)
        print(f"  • {agent_name}: {type(agent).__name__}")
    
    return True


def test_multi_agent_system():
    """测试 Multi-Agent System"""
    print("\n⚙️  测试 Multi-Agent System...\n")
    
    from lianghua_agents.multi_agent_system import (
        WorkflowRequest,
        WorkflowMode,
        get_multi_agent_system,
    )
    
    # 测试 WorkflowMode
    print(f"✓ 支持的工作流模式:")
    for mode in WorkflowMode:
        print(f"  • {mode.value}")
    
    # 测试 WorkflowRequest 创建
    print(f"\n✓ 创建 WorkflowRequest:")
    request = WorkflowRequest(
        mode=WorkflowMode.COMPREHENSIVE,
        ts_code="000001.SZ",
        user_prompt="测试问题",
        horizon="1-3个月",
        risk_level="中等",
    )
    print(f"  请求对象: {type(request).__name__}")
    print(f"  模式: {request.mode.value}")
    print(f"  股票: {request.ts_code}")
    
    # 测试 MultiAgentSystem
    print(f"\n✓ 获取 Multi-Agent System:")
    engine = get_multi_agent_system()
    print(f"  Engine 类型: {type(engine).__name__}")
    
    return True


def test_integration():
    """测试整体集成"""
    print("\n🔗 测试系统整体集成...\n")
    
    from lianghua_agents.multi_agent_system import WorkflowRequest, WorkflowMode, get_multi_agent_system
    from lianghua_agents.prompt_manager import PromptManager
    from lianghua_agents.agent_orchestrator import get_orchestrator
    
    print("✓ Prompt Manager + Agent Orchestrator:")
    prompts = PromptManager.list_templates()
    agents = get_orchestrator().list_agents()
    print(f"  Prompt 数: {len(prompts)}, Agent 数: {len(agents)}")
    
    print(f"\n✓ Multi-Agent System 初始化:")
    engine = get_multi_agent_system()
    print(f"  引擎状态: OK")
    
    print(f"\n✓ WorkflowRequest 创建:")
    request = WorkflowRequest(
        mode=WorkflowMode.COMPREHENSIVE,
        ts_code="000001.SZ",
        user_prompt="模拟请求",
    )
    print(f"  请求类型: {type(request).__name__}")
    print(f"  包含的参数: {len(request.__dict__)} 个")
    
    return True


def main():
    """主函数"""
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║         lianghua 本地验证测试                                         ║
║                                                                       ║
║  这个测试不需要 API 调用，只验证系统框架是否正确加载                  ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    tests = [
        ("模块导入", test_imports),
        ("Prompt Manager", test_prompt_manager),
        ("Agent Orchestrator", test_agent_orchestrator),
        ("Multi-Agent System", test_multi_agent_system),
        ("系统集成", test_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*70}")
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 输出总结
    print(f"\n{'='*70}")
    print("\n📊 测试总结\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}")
    
    print(f"\n总计: {passed}/{total} 通过\n")
    
    if passed == total:
        print("✅ 所有本地测试通过! 系统框架完全正常。")
        print("\n下一步:")
        print("  1. 修复 API 配置问题: python examples/diagnose.py")
        print("  2. 参考故障排查: 查看 TROUBLESHOOTING.md")
        print("  3. 运行完整演示: python examples/run_unified_workflow.py")
        return 0
    else:
        print("❌ 有些测试失败，请检查上面的错误信息")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n👋 已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
