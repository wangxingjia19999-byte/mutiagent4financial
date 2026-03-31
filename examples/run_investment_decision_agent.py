from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.investment_decision_agent import InvestmentDecisionAgent


def main() -> None:
    load_dotenv()
    agent = InvestmentDecisionAgent()

    result = agent.analyze_stock_for_investment(
        ts_code="000001.SZ",
        start_date="20260301",
        end_date="20260331",
        price_limit=120,
        news_limit=12,
        finance_limit=8,
        use_rag=True,
        rag_top_k=4,
        context={"horizon": "1-3个月", "risk_level": "中等"},
    )
    print(result)


if __name__ == "__main__":
    main()
