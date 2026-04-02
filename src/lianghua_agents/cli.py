"""
lianghua CLI - 命令行商股票分析工具
支持通过参数或交互模式运行
"""
from datetime import datetime, timedelta
from pathlib import Path
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner

try:
    from .investment_decision_agent import InvestmentDecisionAgent
    from .multi_agent_system import WorkflowMode, WorkflowRequest, get_multi_agent_system
    from .paper_trading import PaperTradingEngine
except ImportError:
    current_dir = Path(__file__).resolve().parent
    src_dir = current_dir.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from lianghua_agents.investment_decision_agent import InvestmentDecisionAgent
    from lianghua_agents.multi_agent_system import WorkflowMode, WorkflowRequest, get_multi_agent_system
    from lianghua_agents.paper_trading import PaperTradingEngine

console = Console()


def get_default_dates() -> tuple[str, str]:
    """获取默认日期：30天前到今天（YYYYMMDD 格式）"""
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)
    return thirty_days_ago.strftime("%Y%m%d"), today.strftime("%Y%m%d")


@click.group()
def cli():
    """lianghua 量化分析 CLI"""
    pass


def normalize_ts_code(code_input: str, interactive: bool = False) -> str:
    """将用户输入转换为标准 ts_code 格式。"""
    code_input = code_input.strip()
    if not code_input:
        code_input = "000001"
    
    if "." in code_input:
        return code_input
    
    if not code_input.isdigit():
        raise click.BadParameter(f"无效的股票代码格式: {code_input}")
    
    if interactive:
        console.print(f"  输入的股票代码: [bold blue]{code_input}[/bold blue]")
        exchange = click.prompt(
            "  请选择交易所",
            type=click.Choice(["1", "2"], case_sensitive=False),
            default="1",
            show_choices=True
        )
        exchange_name = "SH" if exchange == "2" else "SZ"
    else:
        exchange_name = "SZ"
    
    return f"{code_input}.{exchange_name}"


@cli.command(name="chat")
@click.option(
    "--stock-code",
    "-s",
    type=str,
    help="股票代码（仅数字如 000001，或完整如 000001.SZ）",
)
def chat(stock_code):
    """对话模式：直接输入提示词进行多轮交互"""
    
    console.print(Panel.fit(
        "[bold cyan]lianghua 对话分析[/bold cyan]",
        border_style="cyan"
    ))
    
    stock_code_provided = bool(stock_code)
    if not stock_code:
        stock_code = click.prompt(
            "请输入股票代码（仅数字如 000001，或完整如 000001.SZ）",
            default="000001"
        )
    
    stock_code = normalize_ts_code(stock_code, interactive=not stock_code_provided)
    default_start, default_end = get_default_dates()
    
    console.print(f"\n✓ 已选择股票: [bold cyan]{stock_code}[/bold cyan]")
    console.print(f"✓ 时间范围: [green]{default_start}[/green] ~ [green]{default_end}[/green]")
    console.print("\n[yellow]输入 'help' 查看命令，'exit' 退出[/yellow]\n")
    
    agent = InvestmentDecisionAgent()
    
    while True:
        try:
            user_prompt = click.prompt("[bold cyan]>>> 请输入你的分析需求[/bold cyan]", default="").strip()
            
            if not user_prompt:
                continue
            
            if user_prompt.lower() == "exit":
                console.print("[yellow]再见！[/yellow]")
                break
            
            if user_prompt.lower() == "help":
                _print_help()
                continue
            
            console.print()
            with console.status("[bold green]正在分析...", spinner="dots"):
                result = agent.analyze_stock_for_investment(
                    ts_code=stock_code,
                    start_date=default_start,
                    end_date=default_end,
                    price_limit=120,
                    news_limit=12,
                    finance_limit=8,
                    use_rag=True,
                    rag_top_k=4,
                    context={
                        "custom_prompt": user_prompt,
                        "horizon": "1-3个月",
                        "risk_level": "中等",
                    },
                )
            
            console.print(Panel(result, border_style="cyan"))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]已取消[/yellow]")
            break
        except Exception as exc:
            console.print(f"[red]✗ 错误: {exc}[/red]")


def _print_help():
    """打印帮助信息"""
    help_table = Table(title="命令列表", show_header=True, header_style="bold magenta")
    help_table.add_column("命令", style="cyan")
    help_table.add_column("说明", style="green")
    help_table.add_row("exit", "退出对话")
    help_table.add_row("help", "显示此帮助")
    help_table.add_row("任意文本", "作为分析提示词")
    console.print(help_table)


@cli.command(name="paper")
@click.option(
    "--stock-code",
    "-s",
    type=str,
    required=True,
    help="股票代码（仅数字如 000001，或完整如 000001.SZ）",
)
@click.option(
    "--start-date",
    type=str,
    help="开始日期（YYYYMMDD 格式，默认30天前）",
)
@click.option(
    "--end-date",
    type=str,
    help="结束日期（YYYYMMDD 格式，默认今天）",
)
@click.option(
    "--risk-level",
    type=click.Choice(["保守", "中等", "积极"], case_sensitive=False),
    default="中等",
    show_default=True,
    help="风险偏好，影响目标仓位",
)
@click.option(
    "--state-path",
    type=str,
    default=".paper_account.json",
    show_default=True,
    help="模拟盘账户状态文件路径",
)
@click.option(
    "--initial-cash",
    type=float,
    default=1000000,
    show_default=True,
    help="首次初始化模拟盘资金",
)
@click.option(
    "--custom-prompt",
    "-p",
    type=str,
    default="",
    help="附加给总调智能体的提示词",
)
def paper(stock_code, start_date, end_date, risk_level, state_path, initial_cash, custom_prompt):
    """模拟盘：分析 + 自动执行一轮交易"""
    default_start, default_end = get_default_dates()
    ts_code = normalize_ts_code(stock_code)
    start_date = start_date or default_start
    end_date = end_date or default_end

    context = {
        "custom_prompt": custom_prompt,
        "horizon": "1-3个月",
        "risk_level": risk_level,
        "use_rag": True,
        "rag_top_k": 4,
    }

    console.print(Panel.fit(
        f"[bold cyan]模拟盘执行[/bold cyan]\n"
        f"股票代码: [cyan]{ts_code}[/cyan]\n"
        f"时间范围: [green]{start_date}[/green] ~ [green]{end_date}[/green]\n"
        f"风险偏好: [yellow]{risk_level}[/yellow]\n"
        f"账户文件: [magenta]{state_path}[/magenta]",
        border_style="cyan"
    ))

    decision_agent = InvestmentDecisionAgent()
    engine = PaperTradingEngine(state_path=state_path, initial_cash=initial_cash)

    with console.status("[bold green]正在生成投资决策并执行模拟交易...", spinner="dots"):
        decision_text = decision_agent.analyze_stock_for_investment(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            price_limit=120,
            news_limit=12,
            finance_limit=8,
            use_rag=True,
            rag_top_k=4,
            context=context,
        )
        run_result = engine.run_once(
            ts_code=ts_code,
            decision_text=decision_text,
            start_date=start_date,
            end_date=end_date,
            risk_level=risk_level,
        )

    console.print(Panel(decision_text, title="总调决策结果", border_style="green"))

    summary = Table(title="模拟盘账户快照", show_header=True, header_style="bold blue")
    summary.add_column("字段", style="cyan")
    summary.add_column("值", style="green")
    summary.add_row("最新价", str(run_result.get("last_price")))
    summary.add_row("信号", str(run_result.get("decision", {}).get("signal")))
    summary.add_row("现金", str(run_result.get("cash")))
    summary.add_row("净值", str(run_result.get("nav")))
    summary.add_row("持仓", str(run_result.get("position") or "无"))
    summary.add_row("本次成交", str(run_result.get("executed_trade") or "无"))
    summary.add_row("止损成交", str(run_result.get("stop_loss_trade") or "无"))
    summary.add_row("状态文件", str(run_result.get("state_path")))
    console.print(summary)


@cli.command(name="analyze")
@click.option(
    "--stock-code",
    "-s",
    type=str,
    help="股票代码（仅数字如 000001，或完整如 000001.SZ）",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["decision", "technical", "fundamental"], case_sensitive=False),
    help="分析模式：decision(总调) / technical(看图看线) / fundamental(财报新闻)",
)
@click.option(
    "--start-date",
    type=str,
    help="开始日期（YYYYMMDD 格式，默认30天前）",
)
@click.option(
    "--end-date",
    type=str,
    help="结束日期（YYYYMMDD 格式，默认今天）",
)
@click.option(
    "--custom-prompt",
    "-p",
    type=str,
    help="自定义分析提示词",
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    help="交互模式（如不指定参数则自动进入）",
)
def analyze(stock_code, mode, start_date, end_date, custom_prompt, interactive):
    """执行股票分析"""
    
    default_start, default_end = get_default_dates()
    
    if not stock_code or not mode or not interactive:
        interactive = (
            not stock_code or not mode
        )
    
    if interactive:
        console.print(Panel.fit(
            "[bold cyan]lianghua 交互式分析[/bold cyan]",
            border_style="cyan"
        ))
        
        mode_map = {
            "1": "decision",
            "2": "technical",
            "3": "fundamental"
        }
        mode_choice = click.prompt(
            "请选择模式",
            type=click.Choice(["1", "2", "3"], case_sensitive=False),
            default="1",
            show_choices=True
        )
        mode = mode_map.get(mode_choice, "decision")
        
        stock_code = click.prompt(
            "请输入股票代码（仅数字如 000001，或完整如 000001.SZ）",
            default="000001"
        )
        console.print(f"  默认时间范围: {default_start} 到 {default_end}")
        start_date = click.prompt(
            "请输入开始日期 YYYYMMDD",
            default=default_start
        )
        end_date = click.prompt(
            "请输入结束日期 YYYYMMDD",
            default=default_end
        )
        custom_prompt = click.prompt(
            "请输入自定义分析提示词（可留空）",
            default=""
        )
        
        stock_code = normalize_ts_code(stock_code, interactive=True)
    else:
        stock_code = normalize_ts_code(stock_code)
    
    if not start_date:
        start_date = default_start
    if not end_date:
        end_date = default_end
    if not custom_prompt:
        custom_prompt = ""
    
    mode = mode.lower()
    
    context = {
        "custom_prompt": custom_prompt,
        "horizon": "1-3个月",
        "risk_level": "中等",
        "use_rag": True,
        "rag_top_k": 4,
    }
    
    try:
        if mode == "technical":
            _run_technical(stock_code, start_date, end_date, context)
        elif mode == "fundamental":
            _run_fundamental(stock_code, start_date, end_date, context)
        else:
            _run_decision(stock_code, start_date, end_date, context)
    except Exception as exc:
        console.print(f"[bold red]✗ 分析失败: {exc}[/bold red]")
        raise click.Abort()


def _run_technical(ts_code: str, start_date: str, end_date: str, context: dict) -> None:
    """运行看图看线模式"""
    console.print(Panel.fit(
        f"[bold yellow]看图看线分析[/bold yellow]\n"
        f"股票代码: [cyan]{ts_code}[/cyan]\n"
        f"时间范围: [green]{start_date}[/green] ~ [green]{end_date}[/green]",
        border_style="yellow"
    ))
    
    with console.status("[bold green]正在分析行情数据...", spinner="dots"):
        request = WorkflowRequest(
            mode=WorkflowMode.TECHNICAL,
            ts_code=ts_code,
            user_prompt=context.get("custom_prompt", "请做技术面分析"),
            start_date=start_date,
            end_date=end_date,
            horizon=context.get("horizon", "1-3个月"),
            risk_level=context.get("risk_level", "中等"),
            use_rag=context.get("use_rag", True),
            rag_top_k=context.get("rag_top_k", 4),
        )
        result = get_multi_agent_system().run(request).get_result("visual") or "未返回技术分析结果"
    
    console.print(Panel(result, title="分析结果", border_style="green"))


def _run_fundamental(ts_code: str, start_date: str, end_date: str, context: dict) -> None:
    """运行财报新闻模式"""
    console.print(Panel.fit(
        f"[bold magenta]财报新闻分析[/bold magenta]\n"
        f"股票代码: [cyan]{ts_code}[/cyan]\n"
        f"时间范围: [green]{start_date}[/green] ~ [green]{end_date}[/green]",
        border_style="magenta"
    ))
    
    with console.status("[bold green]正在分析财报和新闻...", spinner="dots"):
        request = WorkflowRequest(
            mode=WorkflowMode.FUNDAMENTAL,
            ts_code=ts_code,
            user_prompt=context.get("custom_prompt", "请做基本面分析"),
            start_date=start_date,
            end_date=end_date,
            horizon=context.get("horizon", "1-3个月"),
            risk_level=context.get("risk_level", "中等"),
            news_limit=12,
            finance_limit=8,
        )
        result = get_multi_agent_system().run(request).get_result("news") or "未返回基本面分析结果"
    
    console.print(Panel(result, title="分析结果", border_style="magenta"))


def _run_decision(ts_code: str, start_date: str, end_date: str, context: dict) -> None:
    """运行总调决策模式"""
    console.print(Panel.fit(
        f"[bold cyan]综合投资决策[/bold cyan]\n"
        f"股票代码: [cyan]{ts_code}[/cyan]\n"
        f"时间范围: [green]{start_date}[/green] ~ [green]{end_date}[/green]",
        border_style="cyan"
    ))
    
    with console.status("[bold green]正在融合分析...", spinner="dots"):
        request = WorkflowRequest(
            mode=WorkflowMode.COMPREHENSIVE,
            ts_code=ts_code,
            user_prompt=context.get("custom_prompt", "请给出综合投资决策"),
            start_date=start_date,
            end_date=end_date,
            horizon=context.get("horizon", "1-3个月"),
            risk_level=context.get("risk_level", "中等"),
            price_limit=120,
            news_limit=12,
            finance_limit=8,
            use_rag=context.get("use_rag", True),
            rag_top_k=context.get("rag_top_k", 4),
        )
        workflow_result = get_multi_agent_system().run(request)
        result = workflow_result.get_result("decision") or "未返回综合决策结果"
    
    console.print(Panel(result, title="投资决策结果", border_style="cyan"))


if __name__ == "__main__":
    cli()
