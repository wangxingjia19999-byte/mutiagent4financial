#!/usr/bin/env python3
"""CrewAI 工作流示例入口。"""
from pathlib import Path
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


from lianghua_agents.crewai_workflow import CrewAIIntegrationError, run_crewai_comprehensive


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行 CrewAI 综合分析")
    parser.add_argument("prompt", help="分析提示词")
    parser.add_argument("-s", "--stock", default="000001.SZ", help="股票代码")
    parser.add_argument("-H", "--horizon", default="1-3个月", help="投资周期")
    parser.add_argument("-r", "--risk", default="中等", help="风险偏好")
    parser.add_argument("--start-date", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--days-back", type=int, default=30, help="未指定日期时回溯天数")
    parser.add_argument("--verbose", action="store_true", help="显示 CrewAI 详细日志")
    args = parser.parse_args()

    load_dotenv()

    try:
        result = run_crewai_comprehensive(
            prompt=args.prompt,
            ts_code=args.stock,
            horizon=args.horizon,
            risk_level=args.risk,
            start_date=args.start_date,
            end_date=args.end_date,
            days_back=args.days_back,
            verbose=args.verbose,
        )
        print("\n===== CrewAI 分析结果 =====\n")
        print(result.output)
    except CrewAIIntegrationError as exc:
        print(f"\n❌ CrewAI 集成错误: {exc}")
    except Exception as exc:
        print(f"\n❌ 运行失败: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
