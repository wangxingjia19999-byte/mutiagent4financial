from pathlib import Path
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.financial_news_agent import FinancialNewsAgent
from lianghua_agents.investment_decision_agent import InvestmentDecisionAgent
from lianghua_agents.visual_stock_agent import VisualStockAgent


def get_default_dates() -> tuple[str, str]:
    """获取默认日期：30天前到今天（YYYYMMDD 格式）"""
    today = datetime.now()
    thirty_days_ago = today - timedelta(days=30)
    return thirty_days_ago.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def ask_input(prompt: str, default: str | None = None) -> str:
    raw = input(prompt).strip()
    if raw:
        return raw
    return default or ""


def normalize_ts_code(code_input: str) -> str:
    """将用户输入转换为标准 ts_code 格式。
    如果只输入数字，询问交易所；如果已是完整格式，直接返回。"""
    code_input = code_input.strip()
    if not code_input:
        return "000001.SZ"
    
    if "." in code_input:
        return code_input
    
    if not code_input.isdigit():
        print(f"✗ 无效的股票代码格式: {code_input}")
        return "000001.SZ"
    
    print(f"  输入的股票代码: {code_input}")
    exchange = ask_input("  请选择交易所 [1=深圳(SZ)/2=上海(SH)] (默认1): ", "1").lower()
    if exchange == "2":
        return f"{code_input}.SH"
    return f"{code_input}.SZ"


def main() -> None:
    load_dotenv()

    print("=" * 60)
    print("lianghua 交互式分析")
    print("模式: 1=总调投资决策 2=看图看线 3=财报新闻")
    print("=" * 60)

    mode = ask_input("请选择模式 [1/2/3] (默认1): ", "1")
    code_raw = ask_input("请输入股票代码 (仅数字如 000001，或完整如 000001.SZ): ", "000001")
    ts_code = normalize_ts_code(code_raw)
    
    default_start, default_end = get_default_dates()
    print(f"  默认时间范围: {default_start} 到 {default_end}")
    start_date = ask_input(f"请输入开始日期 YYYYMMDD (默认{default_start}): ", default_start)
    end_date = ask_input(f"请输入结束日期 YYYYMMDD (默认{default_end}): ", default_end)
    custom_prompt = ask_input("请输入你的补充提示词(可留空): ", "")

    if mode == "2":
        use_rag_str = ask_input("是否启用RAG [y/n] (默认y): ", "y").lower()
        use_rag = use_rag_str != "n"
        rag_top_k = int(ask_input("RAG top_k (默认4): ", "4"))
        limit = int(ask_input("K线条数 limit (默认120): ", "120"))

        agent = VisualStockAgent()
        result = agent.analyze_stock(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
        )
    elif mode == "3":
        news_limit = int(ask_input("新闻条数 news_limit (默认12): ", "12"))
        finance_limit = int(ask_input("财报期数 finance_limit (默认8): ", "8"))
        horizon = ask_input("分析周期描述 (默认1-3个月): ", "1-3个月")

        agent = FinancialNewsAgent()
        result = agent.analyze_stock_with_news_reports(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            news_limit=news_limit,
            finance_limit=finance_limit,
            context={"horizon": horizon, "custom_prompt": custom_prompt},
        )
    else:
        price_limit = int(ask_input("K线条数 price_limit (默认120): ", "120"))
        news_limit = int(ask_input("新闻条数 news_limit (默认12): ", "12"))
        finance_limit = int(ask_input("财报期数 finance_limit (默认8): ", "8"))
        use_rag_str = ask_input("是否启用RAG [y/n] (默认y): ", "y").lower()
        use_rag = use_rag_str != "n"
        rag_top_k = int(ask_input("RAG top_k (默认4): ", "4"))
        horizon = ask_input("分析周期描述 (默认1-3个月): ", "1-3个月")
        risk_level = ask_input("风险偏好 (默认中等): ", "中等")

        agent = InvestmentDecisionAgent()
        result = agent.analyze_stock_for_investment(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            price_limit=price_limit,
            news_limit=news_limit,
            finance_limit=finance_limit,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
            context={
                "horizon": horizon,
                "risk_level": risk_level,
                "use_rag": use_rag,
                "rag_top_k": rag_top_k,
                "custom_prompt": custom_prompt,
            },
        )

    print("\n" + "=" * 60)
    print("分析结果")
    print(f"股票代码: {ts_code}")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
