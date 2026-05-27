#!/usr/bin/env python3
"""
Paper Trading Runner — backtest, single cycle, or continuous auto-trading via Alpaca.

Usage:
    # Full-market trading (auto-fetch all liquid stocks)
    python run_paper_trading.py --mode backtest --universe sp500 --start 2024-01-01 --end 2024-03-01
    python run_paper_trading.py --mode once --universe nasdaq100
    python run_paper_trading.py --mode continuous --universe liquid --interval 300

    # Manual symbol list
    python run_paper_trading.py --mode backtest --symbol AAPL,MSFT,GOOGL --start 2024-01-01 --end 2024-03-01
    python run_paper_trading.py --mode once --symbol AAPL,MSFT,GOOGL
"""

import argparse
import warnings
import logging
import sys
from pathlib import Path

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


# Ensure project root is on path for market_universe import
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def resolve_symbols(args) -> list:
    """Resolve the symbol list from --universe or --symbol."""
    if args.universe:
        from agent_pools.market_universe import get_market_universe_cached

        print(f"\n  Fetching market universe: {args.universe} ...")
        symbols = get_market_universe_cached(
            scope=args.universe,
            apply_filters=not args.no_filter,
        )
        if not symbols:
            print("  ERROR: No symbols returned from Alpaca. Check API keys or try --symbol.")
            sys.exit(1)
        print(f"  Loaded {len(symbols)} symbols (e.g. {', '.join(symbols[:10])}...)")
        return symbols

    return [s.strip() for s in args.symbol.split(",")]


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
        print(f"\n  Target Weights (top {min(15, len(tw))}):")
        for s, w in list(tw.items())[:15]:
            print(f"    {s}: {w:.1%}")
        if len(tw) > 15:
            print(f"    ... and {len(tw) - 15} more")

    rl = result.get("risk_level", "?")
    print(f"\n  Risk Level: {rl}")

    ec = result.get("exit_candidates", [])
    if ec:
        print(f"  Exit Candidates: {len(ec)} symbols")

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
        print(f"\n  Target Weights ({len(tw)} positions):")
        for s, w in list(tw.items())[:15]:
            print(f"    {s}: {w:.1%}")

    decisions = result.get("decisions", [])
    if decisions:
        print(f"\n  Decisions ({len(decisions)}):")
        for d in decisions[:20]:
            print(f"    {d['action']} {d['symbol']} x{d['qty']}  ({d['reason']})")
        if len(decisions) > 20:
            print(f"    ... and {len(decisions) - 20} more")

    executions = result.get("executions", [])
    if executions:
        print(f"\n  Executions ({len(executions)}):")
        for e in executions[:20]:
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
            for p in positions[:20]:
                sym = getattr(p, 'symbol', '?')
                qty = getattr(p, 'qty', 0)
                mv = getattr(p, 'market_value', 0)
                price = getattr(p, 'current_price', 0)
                print(f"    {sym:<6} {float(qty):>8.1f} sh  @ ${float(price):.2f}  = ${float(mv):>10,.0f}")
            if len(positions) > 20:
                print(f"    ... and {len(positions) - 20} more")
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

    # Universe vs explicit symbols
    parser.add_argument(
        "--universe", type=str, default=None,
        choices=["nasdaq100", "sp500", "liquid", "all"],
        help="Auto-fetch tradeable stocks from Alpaca. Overrides --symbol.",
    )
    parser.add_argument(
        "--symbol", type=str, default="AAPL,MSFT",
        help="Stock symbols, comma-separated (ignored if --universe is set).",
    )
    parser.add_argument(
        "--no-filter", action="store_true",
        help="Skip price/volume filtering when using --universe.",
    )

    parser.add_argument(
        "--start", type=str, default="2024-01-01",
        help="Start date YYYY-MM-DD (backtest mode only).",
    )
    parser.add_argument(
        "--end", type=str, default="2024-03-01",
        help="End date YYYY-MM-DD (backtest mode only).",
    )
    parser.add_argument(
        "--capital", type=float, default=100000.0,
        help="Initial/total capital (default: 100000).",
    )
    parser.add_argument(
        "--interval", type=int, default=300,
        help="Seconds between trading cycles in continuous mode (default: 300).",
    )
    parser.add_argument(
        "--max-positions", type=int, default=20,
        help="Maximum number of positions to hold (default: 20).",
    )
    parser.add_argument(
        "--rolling", action="store_true",
        help="Use rolling weekly inference in backtest mode.",
    )

    args = parser.parse_args()
    symbols = resolve_symbols(args)

    print("=" * 50)
    print("  LIANGHUA Paper Trading System")
    print("=" * 50)
    print(f"  Mode:         {args.mode.upper()}")
    print(f"  Symbols:      {len(symbols)} stocks")
    if len(symbols) <= 20:
        print(f"                {', '.join(symbols)}")
    else:
        print(f"                {', '.join(symbols[:10])} ... (+{len(symbols) - 10} more)")
    print(f"  Capital:      ${args.capital:,.0f}")
    if args.mode == "backtest":
        print(f"  Period:       {args.start} -> {args.end}")
        if args.rolling:
            print(f"  Method:       Rolling Weekly")
    elif args.mode == "continuous":
        print(f"  Interval:     {args.interval}s")
    print(f"  MaxPositions: {args.max_positions}")
    print("=" * 50)

    # Initialize orchestrator
    print("\nInitializing orchestrator...")
    orch = Orchestrator()
    print("Ready.\n")

    # Show account for live modes
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
