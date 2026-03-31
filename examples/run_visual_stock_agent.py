from pathlib import Path
import sys

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lianghua_agents.visual_stock_agent import VisualStockAgent


def main() -> None:
    load_dotenv()
    agent = VisualStockAgent()

    result = agent.analyze_stock(
        ts_code="000001.SZ",
        start_date="20251001",
        end_date="20260331",
        limit=120,
    )
    print(result)


if __name__ == "__main__":
    main()
