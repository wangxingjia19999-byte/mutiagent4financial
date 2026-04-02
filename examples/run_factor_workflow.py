#!/usr/bin/env python3
"""因子挖掘工作流示例：挖掘 -> 回测 -> 入池。"""
from pathlib import Path
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def default_dates(days_back: int = 360) -> tuple[str, str]:
    today = datetime.now()
    start = today - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="运行因子挖掘 + 回测 + 因子池入池")
    parser.add_argument("-s", "--stock", default="000001.SZ", help="股票代码")
    parser.add_argument("--start-date", default=None, help="开始日期 YYYYMMDD")
    parser.add_argument("--end-date", default=None, help="结束日期 YYYYMMDD")
    parser.add_argument("--data-limit", type=int, default=360, help="因子数据长度")
    parser.add_argument("--holding-days", type=int, default=5, help="未来收益持有天数")
    parser.add_argument("--min-ic", type=float, default=0.03, help="入池 IC 绝对值下限")
    parser.add_argument("--min-sharpe", type=float, default=0.3, help="入池 Sharpe 下限")
    parser.add_argument("--min-win-rate", type=float, default=0.5, help="入池胜率下限")
    parser.add_argument("--pool-path", default=".factor_pool.json", help="因子池文件路径")
    args = parser.parse_args()

    load_dotenv()

    from lianghua_agents.multi_agent_system import WorkflowMode, WorkflowRequest, get_multi_agent_system

    start_date, end_date = args.start_date, args.end_date
    if not start_date or not end_date:
        start_date, end_date = default_dates(days_back=max(args.data_limit, 360))

    request = WorkflowRequest(
        mode=WorkflowMode.FACTOR,
        ts_code=args.stock,
        user_prompt="执行因子挖掘与回测",
        start_date=start_date,
        end_date=end_date,
        factor_data_limit=args.data_limit,
        factor_holding_days=args.holding_days,
        factor_min_ic_abs=args.min_ic,
        factor_min_sharpe=args.min_sharpe,
        factor_min_win_rate=args.min_win_rate,
        factor_pool_path=args.pool_path,
    )

    result = get_multi_agent_system().run(request)
    print(f"\n状态: {result.status}")
    for name, output in result.results.items():
        print("\n" + "=" * 70)
        print(f"【{name.upper()}】")
        print("=" * 70)
        print(output[:4000])

    if result.errors:
        print("\n错误信息:")
        for k, v in result.errors.items():
            print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
