from dotenv import load_dotenv

from lianghua_agents.quant_agent import QuantResearchAgent


def main() -> None:
    load_dotenv()

    agent = QuantResearchAgent()

    market_snapshot = (
        "BTC 4H: MA20 上穿 MA60，成交量温和放大；"
        "RSI 62；宏观面中性偏多。"
    )
    output = agent.analyze(
        symbol="BTCUSDT",
        market_snapshot=market_snapshot,
        context={"strategy": "中短周期趋势+回撤保护"},
    )

    print(output)


if __name__ == "__main__":
    main()
