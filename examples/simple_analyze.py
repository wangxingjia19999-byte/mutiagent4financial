#!/usr/bin/env python3
"""
极简 Agent 系统 - 只需要输入提示词，自动处理一切
"""
from pathlib import Path
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from dotenv import load_dotenv
load_dotenv()

from lianghua_agents.multi_agent_system import (
    WorkflowRequest,
    WorkflowMode,
    get_multi_agent_system,
)

# 默认参数（用户不需要关心）
DEFAULT_STOCK = "000001.SZ"
DEFAULT_HORIZON = "1-3个月"
DEFAULT_RISK = "中等"


def get_default_dates():
    """获取默认日期"""
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)
    return thirty_days_ago.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def analyze_simple(
    prompt: str,
    ts_code: str = DEFAULT_STOCK,
    horizon: str = DEFAULT_HORIZON,
    risk_level: str = DEFAULT_RISK,
) -> str:
    """
    极简分析函数 - 只需要提供提示词
    
    Args:
        prompt: 你的分析问题（必填）
        ts_code: 股票代码（默认：000001.SZ）
        horizon: 投资周期（默认：1-3个月）
        risk_level: 风险偏好（默认：中等）
    
    Returns:
        分析结果文本
    
    示例:
        result = analyze_simple("这支股票值得投资吗？")
        print(result)
    """
    start_date, end_date = get_default_dates()
    
    # 创建分析请求
    request = WorkflowRequest(
        mode=WorkflowMode.COMPREHENSIVE,  # 自动使用综合分析
        ts_code=ts_code,
        user_prompt=prompt,
        start_date=start_date,
        end_date=end_date,
        horizon=horizon,
        risk_level=risk_level,
        use_rag=True,
        rag_top_k=4,
    )
    
    # 运行分析
    engine = get_multi_agent_system()
    result = engine.run(request)
    
    # 格式化输出
    output = []
    output.append(f"\n📊 股票分析报告: {ts_code}\n")
    output.append("=" * 70)
    
    if result.is_success():
        output.append(f"\n✅ 分析状态: 成功\n")
        
        for agent_name, agent_result in result.results.items():
            output.append(f"\n【{agent_name.upper()}】\n")
            output.append("-" * 70)
            output.append(agent_result)
            output.append("\n")
    else:
        output.append(f"\n⚠️ 分析状态: {result.status}\n")
        
        if result.results:
            for agent_name, agent_result in result.results.items():
                output.append(f"\n【{agent_name.upper()}】\n")
                output.append("-" * 70)
                output.append(agent_result)
                output.append("\n")
        
        if result.errors:
            output.append("\n【错误信息】\n")
            for agent_name, error in result.errors.items():
                output.append(f"  {agent_name}: {error}\n")
    
    output.append("=" * 70)
    
    return "\n".join(output)


def interactive_mode():
    """交互模式 - 持续接收用户输入"""
    from rich.console import Console
    from rich.panel import Panel
    
    console = Console()
    
    console.print(Panel.fit(
        "[bold cyan]lianghua AI 分析助手[/bold cyan]\n"
        "[yellow]只需输入你的问题，我来分析一切[/yellow]",
        border_style="cyan"
    ))
    
    # 获取股票代码（可选）
    stock_input = input("\n📊 股票代码 (默认 000001.SZ): ").strip() or DEFAULT_STOCK
    if "." not in stock_input:
        stock_input = f"{stock_input}.SZ"
    
    console.print(f"\n✓ 已选择股票: [bold cyan]{stock_input}[/bold cyan]\n")
    console.print("[yellow]输入你的分析问题 (输入 'exit' 退出)[/yellow]\n")
    
    while True:
        try:
            prompt = input(">>> ").strip()
            
            if not prompt:
                continue
            
            if prompt.lower() == "exit":
                console.print("[yellow]再见！[/yellow]")
                break
            
            console.print("\n[bold green]正在分析...[/bold green]\n")
            result = analyze_simple(prompt, ts_code=stock_input)
            console.print(result)
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]已取消[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]✗ 错误: {e}[/red]\n")


def main():
    """主程序"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="lianghua 极简分析系统 - 只需输入提示词",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互模式
  python simple_analyze.py

  # 命令行模式
  python simple_analyze.py "这支股票值得投资吗？" -s 000001

  # 指定所有参数
    python simple_analyze.py "技术面分析" -s 000001.SZ -H "1-3个月" -r 中等
        """
    )
    
    parser.add_argument("prompt", nargs="?", help="分析提示词（如果不提供则进入交互模式）")
    parser.add_argument("-s", "--stock", default=DEFAULT_STOCK, help=f"股票代码 (默认: {DEFAULT_STOCK})")
    parser.add_argument("-H", "--horizon", default=DEFAULT_HORIZON, help=f"投资周期 (默认: {DEFAULT_HORIZON})")
    parser.add_argument("-r", "--risk", default=DEFAULT_RISK, help=f"风险偏好 (默认: {DEFAULT_RISK})")
    
    args = parser.parse_args()
    
    try:
        if args.prompt:
            # 命令行模式
            result = analyze_simple(
                prompt=args.prompt,
                ts_code=args.stock,
                horizon=args.horizon,
                risk_level=args.risk,
            )
            print(result)
        else:
            # 交互模式
            interactive_mode()
    
    except KeyboardInterrupt:
        print("\n👋 程序已退出")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
