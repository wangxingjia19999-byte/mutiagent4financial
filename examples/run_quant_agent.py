from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

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
