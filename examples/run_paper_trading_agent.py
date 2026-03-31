from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.investment_decision_agent import InvestmentDecisionAgent
from lianghua_agents.paper_trading import PaperTradingEngine


def main() -> None:
    load_dotenv()

    ts_code = "000001.SZ"
    start_date = "20260301"
    end_date = "20260331"

    decision_agent = InvestmentDecisionAgent()
    engine = PaperTradingEngine(state_path=".paper_account.json", initial_cash=1_000_000)

    decision_text = decision_agent.analyze_stock_for_investment(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        price_limit=120,
        news_limit=12,
        finance_limit=8,
        use_rag=True,
        rag_top_k=4,
        context={"horizon": "1-3个月", "risk_level": "中等"},
    )

    result = engine.run_once(
        ts_code=ts_code,
        decision_text=decision_text,
        start_date=start_date,
        end_date=end_date,
        risk_level="中等",
    )

    print("=== 决策结果 ===")
    print(decision_text)
    print("\n=== 模拟盘执行结果 ===")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
