from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "agent_pools" / "risk_agent_demo" / "example_usage.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Demo entry not found: {TARGET}")

runpy.run_path(str(TARGET), run_name="__main__")
