from pathlib import Path
import runpy
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / "agent_pools" / "risk_agent_demo" / "example_usage.py"

    if not target.exists():
        raise FileNotFoundError(f"Demo entry not found: {target}")

    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    sys.exit(main())
