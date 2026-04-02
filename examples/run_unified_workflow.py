#!/usr/bin/env python3
"""
统一工作流示例 - 展示如何通过统一的 prompt 系统运行 Agent
"""
from pathlib import Path
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.multi_agent_system import (
    WorkflowRequest,
    WorkflowMode,
    get_multi_agent_system,
)
from lianghua_agents.prompt_manager import PromptManager


def print_header(text: str):
    """打印标题"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_result(result):
    """打印结果"""
    print(f"状态: {result.status.upper()}")
    
    if result.results:
        print(f"\n【分析结果】")
        for agent_name, output in result.results.items():
            print(f"\n--- {agent_name} ---")
            # 打印前500个字符
            output_preview = output[:500] + "..." if len(output) > 500 else output
            print(output_preview)
    
    if result.errors:
        print(f"\n【错误】")
        for agent_name, error in result.errors.items():
            print(f"  {agent_name}: {error}")


def get_default_dates() -> tuple[str, str]:
    """获取默认日期"""
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)
    return thirty_days_ago.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def demo_prompts():
    """演示 Prompt Manager"""
    print_header("Prompt Manager 演示")
    
    # 列出所有可用的提示词
    print("📋 可用的 Agent Prompt 模板：\n")
    for template_name in PromptManager.list_templates():
        template = PromptManager.get_template(template_name)
        print(f"  • {template.name} (v{template.version})")
        print(f"    描述: {template.metadata.get('agent_type', 'N/A')}")
    
    # 演示渲染提示词
    print("\n\n📝 技术面分析 Agent 的 Prompt 范例：\n")
    prompt = PromptManager.render_system_prompt(
        "visual_stock_agent",
        horizon="1-3个月",
        risk_level="中等",
    )
    print(prompt)


def demo_single_agent_mode():
    """演示单 Agent 模式"""
    print_header("单 Agent 模式演示 - 只运行决策 Agent")
    
    start_date, end_date = get_default_dates()
    
    request = WorkflowRequest(
        mode=WorkflowMode.SINGLE,
        ts_code="000001.SZ",
        user_prompt="这支股票最近表现如何？是否值得投资？",
        start_date=start_date,
        end_date=end_date,
        horizon="1-3个月",
        risk_level="中等",
        extra_context={"agent_name": "decision"},  # 指定运行的 Agent
    )
    
    print(f"📊 分析股票: {request.ts_code}")
    print(f"📅 时间范围: {request.start_date} ~ {request.end_date}")
    print(f"💬 用户提示: {request.user_prompt}\n")
    
    engine = get_multi_agent_system()
    result = engine.run(request)
    
    print_result(result)


def demo_technical_only():
    """演示技术面分析"""
    print_header("技术面分析 - 仅看图看线")
    
    start_date, end_date = get_default_dates()
    
    request = WorkflowRequest(
        mode=WorkflowMode.TECHNICAL,
        ts_code="000001.SZ",
        user_prompt="从技术面看，这支股票的短期走势如何？",
        start_date=start_date,
        end_date=end_date,
        horizon="3-5个交易日",  # 短期技术分析
        risk_level="中等",
    )
    
    print(f"📊 分析股票: {request.ts_code}")
    print(f"📅 时间范围: {request.start_date} ~ {request.end_date}")
    print(f"💬 用户提示: {request.user_prompt}\n")
    
    engine = get_multi_agent_system()
    result = engine.run(request)
    
    print_result(result)


def demo_fundamental_only():
    """演示基本面分析"""
    print_header("基本面分析 - 财报与新闻")
    
    start_date, end_date = get_default_dates()
    
    request = WorkflowRequest(
        mode=WorkflowMode.FUNDAMENTAL,
        ts_code="000001.SZ",
        user_prompt="基本面看，这支股票未来3个月有投资机会吗？",
        start_date=start_date,
        end_date=end_date,
        horizon="1-3个月",
        risk_level="中等",
    )
    
    print(f"📊 分析股票: {request.ts_code}")
    print(f"📅 时间范围: {request.start_date} ~ {request.end_date}")
    print(f"💬 用户提示: {request.user_prompt}\n")
    
    engine = get_multi_agent_system()
    result = engine.run(request)
    
    print_result(result)


def demo_comprehensive():
    """演示综合分析"""
    print_header("综合分析 - 技术+基本面+决策")
    
    start_date, end_date = get_default_dates()
    
    request = WorkflowRequest(
        mode=WorkflowMode.COMPREHENSIVE,
        ts_code="000001.SZ",
        user_prompt="综合分析，这支股票现在是否可以建仓？建议什么时候介入？",
        start_date=start_date,
        end_date=end_date,
        horizon="1-3个月",
        risk_level="中等",
        strategy="趋势跟随 + 风险控制",
        use_rag=True,  # 启用知识库增强
        rag_top_k=4,
    )
    
    print(f"📊 分析股票: {request.ts_code}")
    print(f"📅 时间范围: {request.start_date} ~ {request.end_date}")
    print(f"💬 用户提示: {request.user_prompt}")
    print(f"⚙️  参数: horizon={request.horizon}, risk_level={request.risk_level}\n")
    
    engine = get_multi_agent_system()
    result = engine.run(request)
    
    print_result(result)


def main():
    """主函数"""
    from dotenv import load_dotenv
    load_dotenv()
    
    print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                   lianghua 统一工作流引擎演示                          ║
║                                                                       ║
║  这个演示展示如何通过统一的 Workflow 系统使用 Agent                     ║
║  - 集中管理所有 Prompt 模板                                           ║
║  - 支持不同的分析模式（单Agent/技术/基本面/综合）                      ║
║  - 通过完整的 prompt 和参数推动整个分析流程                            ║
╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    # 选择要运行的演示
    print("\n📋 可用的演示模式：\n")
    demos = {
        "1": ("Prompt Manager 演示", demo_prompts),
        "2": ("单 Agent 模式", demo_single_agent_mode),
        "3": ("技术面分析", demo_technical_only),
        "4": ("基本面分析", demo_fundamental_only),
        "5": ("综合分析", demo_comprehensive),
    }
    
    for key, (name, _) in demos.items():
        print(f"  {key}. {name}")
    print(f"  0. 运行所有演示")
    
    choice = input("\n👉 请选择 [0-5]: ").strip() or "0"
    
    try:
        if choice == "0":
            # 运行所有演示
            for key in ["1", "2", "3", "4", "5"]:
                if key in demos:
                    name, func = demos[key]
                    try:
                        func()
                    except Exception as e:
                        print(f"\n❌ {name} 出错: {e}")
                        import traceback
                        traceback.print_exc()
        elif choice in demos:
            name, func = demos[choice]
            func()
        else:
            print("❌ 无效的选择")
    
    except KeyboardInterrupt:
        print("\n\n👋 演示已取消")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
