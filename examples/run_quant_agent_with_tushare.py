from dotenv import load_dotenv

from lianghua_agents.quant_agent import QuantResearchAgent


def main() -> None:
    load_dotenv()

    agent = QuantResearchAgent()

    result = agent.analyze_stock_with_tushare(
        ts_code="000001.SZ",
        start_date="20260101",
        end_date="20260331",
        limit=30,
        context={"strategy": "日线趋势+回撤控制"},
    )
    print(result)


if __name__ == "__main__":
    main()
