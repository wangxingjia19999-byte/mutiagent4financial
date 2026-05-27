#!/usr/bin/env python3
"""
Paper Trading Runner — backtest, single cycle, or continuous auto-trading via Alpaca.

Usage:
    python run_paper_trading.py --mode backtest --symbol AAPL,MSFT --start 2024-01-01 --end 2024-03-01
    python run_paper_trading.py --mode once --symbol AAPL,MSFT,GOOGL
    python run_paper_trading.py --mode continuous --symbol AAPL,MSFT,GOOGL,TSLA --interval 300
"""

import argparse
import warnings
import logging

warnings.filterwarnings("ignore")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("alpaca").setLevel(logging.WARNING)

from dotenv import load_dotenv

load_dotenv()

from agent_pools.poe_config import setup_poe_env

setup_poe_env()

from orchestrator_demo.orchestrator import Orchestrator
from agent_pools.execution_agent_demo.execution_agent_demo.execution_agent import (
    market_status_str,
    alpaca_service,
)


def print_backtest_result(result):
    """Display backtest results."""
    print("\n" + "-" * 40)
    print("  BACKTEST RESULTS")
    print("-" * 40)

    if result.get("status") != "success":
        print(f"  Status: {result.get('status')}")
        print(f"  Message: {result.get('message', 'N/A')}")
        return

    m = result.get("performance_metrics", {})
    print(f"  Total Return:  {m.get('total_return', 0):.4%}")
    print(f"  Sharpe Ratio:  {m.get('sharpe_ratio', 0):.4f}")
    print(f"  Max Drawdown:  {m.get('max_drawdown', 0):.4%}")
    print(f"  Volatility:    {m.get('volatility', 0):.4%}")

    tw = result.get("target_weights", {})
    if tw:
        print(f"\n  Target Weights:")
        for s, w in tw.items():
            print(f"    {s}: {w:.1%}")

    rl = result.get("risk_level", "?")
    print(f"\n  Risk Level: {rl}")

    ec = result.get("exit_candidates", [])
    if ec:
        print(f"  Exit Candidates: {', '.join(ec)}")

    print("-" * 40)


def print_once_result(result):
    """Display single-cycle live trading result."""
    print("\n" + "-" * 40)
    print("  LIVE TRADING CYCLE RESULT")
    print("-" * 40)

    print(f"  Cycle:    #{result.get('cycle_id', '?')}")
    print(f"  Status:   {result.get('status')}")
    print(f"  Market:   {result.get('market_status', '?')}")
    print(f"  Risk:     {result.get('risk_level', '?')}")

    tw = result.get("target_weights", {})
    if tw:
        print(f"\n  Target Weights:")
        for s, w in tw.items():
            print(f"    {s}: {w:.1%}")

    decisions = result.get("decisions", [])
    if decisions:
        print(f"\n  Decisions ({len(decisions)}):")
        for d in decisions:
            print(f"    {d['action']} {d['symbol']} x{d['qty']}  ({d['reason']})")

    executions = result.get("executions", [])
    if executions:
        print(f"\n  Executions ({len(executions)}):")
        for e in executions:
            status = e.get("status", "?")
            symbol = e.get("symbol", "?")
            side = e.get("side", "?")
            qty = e.get("qty", 0)
            error = e.get("error", "")
            price = e.get("filled_price", "")
            detail = f"@ ${price}" if price else ""
            if error:
                detail = f"ERROR: {error}"
            print(f"    {symbol} {side} {qty} -> {status} {detail}")

    if result.get("status") == "error":
        print(f"\n  Error: {result.get('message')}")

    print("-" * 40)


def show_account():
    """Show current Alpaca account status."""
    if not alpaca_service:
        print("  Alpaca service not available.")
        return

    try:
        acct = alpaca_service.get_account()
        print("\n" + "=" * 50)
        print("  ALPACA ACCOUNT")
        print("=" * 50)
        print(f"  Buying Power:  ${float(acct.buying_power):,.0f}")
        print(f"  Cash:          ${float(acct.cash):,.0f}")
        print(f"  Portfolio:     ${float(acct.portfolio_value):,.0f}")
        print(f"  Currency:      {acct.currency}")
        print(f"  Market:        {market_status_str()}")

        positions = alpaca_service.get_positions()
        if positions:
            print(f"\n  Positions ({len(positions)}):")
            for p in positions:
                sym = getattr(p, 'symbol', '?')
                qty = getattr(p, 'qty', 0)
                mv = getattr(p, 'market_value', 0)
                price = getattr(p, 'current_price', 0)
                print(f"    {sym:<6} {float(qty):>8.1f} sh  @ ${float(price):.2f}  = ${float(mv):>10,.0f}")
        else:
            print("\n  No open positions.")
        print("=" * 50)
    except Exception as e:
        print(f"  Could not fetch account: {e}")


def main():
    parser = argparse.ArgumentParser(description="LIANGHUA Paper Trading System")

    parser.add_argument(
        "--mode", choices=["backtest", "once", "continuous"], default="backtest",
        help="backtest=historical simulation | once=single live cycle | continuous=auto-trading loop",
    )
    parser.add_argument(
        "--symbol", type=str, default="AAPL,MSFT",
        help="Stock symbols, comma-separated (default: AAPL,MSFT)",
    )
    parser.add_argument(
        "--start", type=str, default="2024-01-01",
        help="Start date YYYY-MM-DD (backtest mode only, default: 2024-01-01)",
    )
    parser.add_argument(
        "--end", type=str, default="2024-03-01",
        help="End date YYYY-MM-DD (backtest mode only, default: 2024-03-01)",
    )
    parser.add_argument(
        "--capital", type=float, default=100000.0,
        help="Initial/total capital (default: 100000)",
    )
    parser.add_argument(
        "--interval", type=int, default=300,
        help="Seconds between trading cycles in continuous mode (default: 300)",
    )
    parser.add_argument(
        "--max-positions", type=int, default=10,
        help="Maximum number of positions to hold (default: 10)",
    )
    parser.add_argument(
        "--rolling", action="store_true",
        help="Use rolling weekly inference in backtest mode",
    )

    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbol.split(",")]

    print("=" * 50)
    print("  LIANGHUA Paper Trading System")
    print("=" * 50)
    print(f"  Mode:        {args.mode.upper()}")
    print(f"  Symbols:     {', '.join(symbols)}")
    print(f"  Capital:     ${args.capital:,.0f}")
    if args.mode == "backtest":
        print(f"  Period:      {args.start} -> {args.end}")
        if args.rolling:
            print(f"  Method:      Rolling Weekly")
    elif args.mode == "continuous":
        print(f"  Interval:    {args.interval}s")
    print(f"  MaxPositions: {args.max_positions}")
    print("=" * 50)

    # Initialize orchestrator
    print("\nInitializing orchestrator...")
    orch = Orchestrator()
    print("Ready.\n")

    # Show account for live modes (after orchestrator init so Alpaca is connected)
    if args.mode in ("once", "continuous"):
        show_account()

    if args.mode == "backtest":
        if args.rolling:
            result = orch.run_inference_rolling_week(
                symbol=symbols,
                start_date=args.start,
                end_date=args.end,
                total_capital=args.capital,
            )
        else:
            result = orch.run_pipeline(
                symbol=symbols,
                start_date=args.start,
                end_date=args.end,
                total_capital=args.capital,
            )
        print_backtest_result(result)

    elif args.mode == "once":
        result = orch.run_live_trading_cycle(
            symbols=symbols,
            total_capital=args.capital,
            max_positions=args.max_positions,
        )
        print_once_result(result)

    elif args.mode == "continuous":
        orch.run_live_trading_loop(
            symbols=symbols,
            total_capital=args.capital,
            interval_seconds=args.interval,
            max_positions=args.max_positions,
        )


if __name__ == "__main__":
    main()
