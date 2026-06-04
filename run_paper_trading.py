#!/usr/bin/env python3
"""
Paper Trading Runner - backtest, single cycle, or continuous auto-trading via Alpaca.

Usage:
    # Full-market trading (auto-fetch all liquid stocks)
    python run_paper_trading.py --mode backtest --universe sp500 --start 2024-01-01 --end 2024-03-01
    python run_paper_trading.py --mode once --universe nasdaq100
    python run_paper_trading.py --mode continuous --universe liquid --interval 300

    # Manual symbol list
    python run_paper_trading.py --mode backtest --symbol AAPL,MSFT,GOOGL --start 2024-01-01 --end 2024-03-01
    python run_paper_trading.py --mode once --symbol AAPL,MSFT,GOOGL

    # Disable RAG or memory
    python run_paper_trading.py --mode backtest --universe sp500 --no-rag --no-memory
"""

import argparse
import os
import warnings
import logging
import sys
from datetime import datetime
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

# Market abstractions (A-share support)
from market import MarketConfig, US_MARKET, CN_MARKET, USMarketCalendar, CNMarketCalendar
from data.providers.alpaca_provider import AlpacaProvider
from data.providers.tushare_provider import TushareProvider
from data.providers.akshare_provider import AkshareProvider
from broker import AlpacaBroker, CNPaperBroker

# Ensure project root is on path for imports
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ═══════════════════════════════════════════════════════════════════════════════
# RAG & Memory Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_rag_client = None
_memory_client = None


def _init_rag(enable: bool = True):
    """Initialize RAG client and pre-build the vector index."""
    global _rag_client
    if not enable:
        return None
    try:
        from agent_pools.memory.agent_rag_client import get_rag_client
        _rag_client = get_rag_client()
        return _rag_client
    except Exception as e:
        print(f"  [RAG] Init failed: {e}")
        return None


def _init_memory(enable: bool = True):
    """Initialize Neo4j memory client."""
    global _memory_client
    if not enable:
        return None
    try:
        from agent_pools.memory.agent_memory_client import AgentMemoryClient
        _memory_client = AgentMemoryClient()
        return _memory_client
    except Exception as e:
        print(f"  [Memory] Init failed: {e}")
        return None


def _close_memory():
    global _memory_client
    if _memory_client:
        try:
            _memory_client.close()
        except Exception:
            pass
        _memory_client = None


def _rag_query(query: str, top_k: int = 3) -> str:
    """Query the RAG knowledge base, return formatted string."""
    if not _rag_client:
        return ""
    try:
        results = _rag_client.query(query, n_results=top_k)
        if not results:
            return ""
        return "\n".join(results)
    except Exception:
        return ""


def _memory_store(strategy_name: str, issue: str, lesson: str):
    """Store a reflection into Neo4j memory."""
    if not _memory_client:
        return
    try:
        _memory_client.store_reflection(
            agent_name="PaperTrading",
            strategy_name=strategy_name,
            issue=issue,
            lesson_learned=lesson,
        )
    except Exception:
        pass


def _memory_lessons(keyword: str) -> list:
    """Query past lessons from Neo4j memory."""
    if not _memory_client:
        return []
    try:
        return _memory_client.retrieve_lessons_by_issue(keyword)
    except Exception:
        return []


def _rag_context_for_mode(mode: str, symbols_count: int) -> str:
    """Build a RAG query string based on the trading mode and parameters."""
    if mode == "backtest":
        return (
            f"factor construction methodology backtesting {symbols_count} stocks "
            f"time series analysis statistical significance"
        )
    else:
        return (
            f"real-time factor trading execution {symbols_count} stocks "
            f"risk management portfolio construction"
        )


def _build_rag_summary(mode: str, symbols_count: int) -> str:
    """Query RAG and return a formatted summary for the agent pipeline."""
    query = _rag_context_for_mode(mode, symbols_count)
    raw = _rag_query(query, top_k=3)
    if not raw:
        return ""
    # Parse each result block: "[source]:\ncontent\n\n[source]:\ncontent\n\n..."
    import re
    blocks = re.split(r"\n(?=\[)", raw.strip())
    summary_lines = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Remove the "[source]:" header line, keep the content
        lines = block.split("\n", 1)
        if len(lines) > 1:
            content = lines[1].strip()[:300]
        else:
            content = lines[0].strip()[:300]
        if content:
            summary_lines.append(f"  - {content}")
    if summary_lines:
        return "Alpha101 Research Insights:\n" + "\n".join(summary_lines[:5])
    return ""


def _store_pipeline_reflections(mode: str, result: dict, symbols_count: int):
    """Store meaningful lessons based on pipeline results."""
    if not _memory_client:
        return

    status = result.get("status", "unknown")

    if status == "success":
        metrics = result.get("performance_metrics", {})
        sharpe = metrics.get("sharpe_ratio", 0)
        ret = metrics.get("total_return", 0)
        mdd = metrics.get("max_drawdown", 0)

        if sharpe > 1.0:
            _memory_store(
                f"{mode}_pipeline",
                "strong_performance",
                f"Sharpe={sharpe:.2f} Return={ret:.2%} on {symbols_count} stocks - "
                f"strategy construction approach is effective",
            )
        elif sharpe < 0:
            _memory_store(
                f"{mode}_pipeline",
                "negative_sharpe",
                f"Sharpe={sharpe:.2f} Return={ret:.2%} on {symbols_count} stocks - "
                f"needs better factor selection or risk control",
            )

        if mdd < -0.3:
            _memory_store(
                f"{mode}_pipeline",
                "large_drawdown",
                f"MaxDrawdown={mdd:.2%} on {symbols_count} stocks - "
                f"add stop-loss or reduce position size during high volatility",
            )

        # Store general cycle info
        _memory_store(
            f"{mode}_pipeline",
            f"cycle_completed",
            f"Completed {mode} cycle on {symbols_count} stocks. "
            f"Sharpe={sharpe:.2f} Return={ret:.2%} MDD={mdd:.2%} "
            f"Risk={result.get('risk_level', '?')}",
        )

    elif status == "error":
        _memory_store(
            f"{mode}_pipeline",
            "pipeline_error",
            f"Error: {result.get('message', 'unknown')} on {symbols_count} stocks",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Symbol Resolution
# ═══════════════════════════════════════════════════════════════════════════════

def resolve_symbols(args) -> list:
    """Resolve the symbol list from --universe or --symbol.

    For large CN universes (all_cn, liquid_cn), automatically runs
    multi-factor pre-screening to narrow down to a manageable subset.
    """
    if args.universe:
        from agent_pools.market_universe import get_market_universe_cached

        # Detect market from universe choice
        cn_scopes = {"csi300", "csi500", "liquid_cn", "all_cn"}
        market = "cn" if args.universe in cn_scopes else args.market

        print(f"\n  Fetching market universe: {args.universe} (market={market}) ...")

        # For full-market CN universes, use multi-factor pre-screening
        if args.universe in ("all_cn", "liquid_cn") and not args.no_filter:
            print("  🧠 Running multi-factor pre-screener (5000+ → 200 candidates)...")
            try:
                from data.providers.full_market_screener import FullMarketScreener
                screener = FullMarketScreener()
                symbols = screener.screen(
                    top_n=getattr(args, 'max_universe', 200),
                    fetch_historical=True,
                )
                if symbols and len(symbols) >= 50:
                    print(f"  ✅ Pre-screened to {len(symbols)} high-quality candidates")
                    print(f"     Top 10: {', '.join(symbols[:10])}")
                    return symbols
                print("  ⚠️  Pre-screener returned insufficient results — falling back to cache")
            except Exception as e:
                print(f"  ⚠️  Pre-screener failed ({e}) — falling back to cache")

        symbols = get_market_universe_cached(
            scope=args.universe,
            apply_filters=not args.no_filter,
            market=market,
        )
        if not symbols:
            source = "Tushare" if market == "cn" else "Alpaca"
            print(f"  ERROR: No symbols returned from {source}. Check API keys or try --symbol.")
            sys.exit(1)

        # If still too many symbols, apply hard cap and warn
        max_universe = getattr(args, 'max_universe', 500)
        if len(symbols) > max_universe:
            print(f"  ⚠️  Truncating {len(symbols)} -> {max_universe} symbols (use --max-universe to adjust)")
            # Take evenly-spaced sample to maintain diversification
            step = len(symbols) // max_universe
            symbols = symbols[::step][:max_universe] if step > 1 else symbols[:max_universe]

        print(f"  Loaded {len(symbols)} symbols (e.g. {', '.join(symbols[:10])}...)")

        # ── Market cap filter (small/mid-cap only) ──
        if getattr(args, 'max_market_cap', None):
            symbols = _apply_market_cap_filter(symbols, args.max_market_cap, market)
            if not symbols:
                print("  ERROR: No symbols passed market cap filter. Try a larger --max-market-cap.")
                sys.exit(1)

        return symbols

    symbols = [s.strip() for s in args.symbol.split(",")]

    # ── Market cap filter (also applies to --symbol lists) ──
    if getattr(args, 'max_market_cap', None):
        sym_market = args.market  # use the explicit --market flag
        symbols = _apply_market_cap_filter(symbols, args.max_market_cap, sym_market)
        if not symbols:
            print("  ERROR: No symbols passed market cap filter. Try a larger --max-market-cap.")
            sys.exit(1)

    return symbols


def _apply_market_cap_filter(symbols: List[str], max_cap_yi: float, market: str) -> List[str]:
    """
    Filter symbols by market cap ≤ max_cap_yi (亿元).

    For CN: 1亿 = ¥100M. Uses provider's spot/snapshot data.
    For US: converts 亿元 to USD (roughly ÷7). Uses Alpaca snapshot or yfinance.
    """
    max_cap_cny = max_cap_yi * 1e8  # convert 亿 to CNY

    if market == "cn":
        return _filter_cn_market_cap(symbols, max_cap_cny)
    else:
        return _filter_us_market_cap(symbols, max_cap_cny)


def _filter_cn_market_cap(symbols: List[str], max_cap_cny: float) -> List[str]:
    """Filter CN stocks by market cap using akshare → Tushare → keep-all fallback."""
    max_cap_yi = max_cap_cny / 1e8

    # ── Method 1: akshare (free, has 总市值 in spot data) ──
    try:
        import akshare as ak
        import requests
        s = requests.Session()
        s.trust_env = False

        spot = ak.stock_zh_a_spot_em()
        if spot is not None and not spot.empty:
            from data.providers.akshare_provider import _normalize_symbol
            spot['symbol'] = spot['代码'].apply(_normalize_symbol)
            spot['total_mv'] = pd.to_numeric(spot['总市值'], errors='coerce')

            spot_filtered = spot[
                (spot['symbol'].isin(symbols)) &
                (spot['total_mv'] > 0) &
                (spot['total_mv'] <= max_cap_cny)
            ]
            passed = spot_filtered['symbol'].tolist()
            if passed:
                excluded = len(symbols) - len(passed)
                avg_cap = spot_filtered['total_mv'].mean() / 1e8
                print(f"  📏 Market cap ≤ {max_cap_yi:.0f}亿: {len(passed)} stocks kept "
                      f"(avg {avg_cap:.0f}亿, excluded {excluded})")
                return passed
    except Exception:
        pass

    # ── Method 2: Tushare daily_basic (one-by-one, free tier doesn't support batch) ──
    try:
        import tushare as ts
        token = os.getenv("TUSHARE_TOKEN", "")
        if token and not token.startswith("os.getenv"):
            ts.set_token(token)
            pro = ts.pro_api()
            today_str = datetime.now().strftime("%Y%m%d")

            passed = []
            total_mvs = []
            for i, sym in enumerate(symbols):
                try:
                    df = pro.daily_basic(ts_code=sym, trade_date=today_str, fields="ts_code,total_mv")
                    if df is not None and not df.empty:
                        mv_wan = float(df['total_mv'].iloc[0])  # 万元
                        mv_cny = mv_wan * 1e4  # → 元
                        if 0 < mv_cny <= max_cap_cny:
                            passed.append(sym)
                            total_mvs.append(mv_cny)
                    if (i + 1) % 50 == 0:
                        print(f"    ... checked {i + 1}/{len(symbols)}")
                except Exception:
                    continue  # skip this stock

            if passed:
                excluded = len(symbols) - len(passed)
                avg_cap = (sum(total_mvs) / len(total_mvs)) / 1e8 if total_mvs else 0
                print(f"  📏 Market cap ≤ {max_cap_yi:.0f}亿 (via Tushare): "
                      f"{len(passed)} stocks kept (avg {avg_cap:.0f}亿, excluded {excluded})")
                return passed
    except Exception:
        pass

    # ── Fallback: keep all ──
    print(f"  ⚠️  Market cap filter unavailable — keeping all {len(symbols)} symbols")
    return symbols


def _filter_us_market_cap(symbols: List[str], max_cap_cny: float) -> List[str]:
    """
    Filter US stocks by approximate market cap.
    Uses yfinance to get market cap (free but slow for large universes).
    Converts CNY cap → USD (roughly 7:1).
    """
    max_cap_usd = max_cap_cny / 7.0  # rough CNY→USD

    try:
        import yfinance as yf

        passed = []
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]
            try:
                tickers = yf.Tickers(" ".join(batch))
                for sym in batch:
                    try:
                        info = tickers.tickers.get(sym, {}).info if hasattr(tickers, 'tickers') else {}
                        if not info:
                            t = yf.Ticker(sym)
                            info = t.info or {}
                        cap = info.get('marketCap', 0) or 0
                        if 0 < cap <= max_cap_usd:
                            passed.append(sym)
                    except Exception:
                        passed.append(sym)  # keep if can't determine
            except Exception:
                passed.extend(batch)  # keep all on batch failure

        excluded = len(symbols) - len(passed)
        print(f"  📏 Market cap ≤ ${max_cap_usd/1e9:.1f}B (≈{max_cap_cny/1e8:.0f}亿): "
              f"{len(passed)} stocks kept (excluded {excluded})")
        return passed

    except Exception as e:
        print(f"  ⚠️  US market cap filter failed ({e}) — keeping all {len(symbols)} symbols")
        return symbols


def _create_market_components(market: str, capital: float, broker_type: str = "paper"):
    """Factory: returns (MarketConfig, DataProvider, Broker, MarketCalendar) for the given market.

    broker_type:
        - "paper" (default): CNPaperBroker or AlpacaBroker (simulation)
        - "emt": EMTBroker with EMQProvider (real A-share API via 东方财富)
        - "alpaca": AlpacaBroker (real US trading)
    """
    if market == "cn":
        config = CN_MARKET
        calendar = CNMarketCalendar()

        if broker_type == "emt":
            # Use real EMT/EMQ API endpoints
            from data.providers.emq_provider import EMQProvider
            from broker.emt_broker import EMTBroker

            provider = EMQProvider()
            broker = EMTBroker(
                initial_capital=capital,
                config=config,
            )
            # Wire up EMT broker with EMQ data for price discovery
            broker._paper._data_provider = provider
            return config, provider, broker, calendar
        else:
            # Paper simulation (default) — try akshare first (free, no token),
            # fall back to Tushare if akshare fails
            provider = AkshareProvider()
            if not provider.is_available:
                print("  ⚠️  Akshare unavailable, trying Tushare...")
                provider = TushareProvider()
            broker = CNPaperBroker(
                initial_capital=capital, config=config, data_provider=provider
            )
            return config, provider, broker, calendar
    else:
        config = US_MARKET
        provider = AlpacaProvider()
        calendar = USMarketCalendar()
        broker = AlpacaBroker(paper=True, config=config)
        return config, provider, broker, calendar


# ═══════════════════════════════════════════════════════════════════════════════
# Display Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def print_banner(args, symbols, rag_enabled, memory_enabled, market_config=None):
    """Print the system startup banner with RAG & Memory status."""
    currency_sym = market_config.currency_symbol if market_config else "$"
    market_name = market_config.market_name if market_config else "US Stocks"

    print("=" * 55)
    print("  LIANGHUA Paper Trading System")
    print("=" * 55)
    print(f"  Market:       {market_name}")
    print(f"  Mode:         {args.mode.upper()}")
    print(f"  Symbols:      {len(symbols)} stocks")
    if len(symbols) <= 20:
        print(f"                {', '.join(symbols)}")
    else:
        print(f"                {', '.join(symbols[:10])} ... (+{len(symbols) - 10} more)")
    print(f"  Capital:      {currency_sym}{args.capital:,.0f}")
    if args.mode == "backtest":
        print(f"  Period:       {args.start} -> {args.end}")
        if args.rolling:
            print(f"  Method:       Rolling Weekly")
    elif args.mode == "continuous":
        print(f"  Interval:     {args.interval}s")
    print(f"  MaxPositions: {args.max_positions}")
    print("-" * 55)
    print(f"  RAG:          {'ONLINE' if rag_enabled else 'OFF'}")
    print(f"  Memory:       {'ONLINE' if memory_enabled else 'OFF'}")
    print("=" * 55)


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
    rs = result.get("risk_score", None)
    regime = result.get("market_regime", "")
    print(f"\n  Risk Level: {rl}", end="")
    if rs is not None:
        print(f" (score={rs:.3f})", end="")
    if regime:
        print(f"  |  Regime: {regime}", end="")
    print()

    narrative = result.get("risk_narrative", "")
    if narrative:
        print(f"  📋 {narrative}")

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
    print(f"  Risk:     {result.get('risk_level', '?')} (score={result.get('risk_score', 0):.3f})")

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


def show_account(broker=None, calendar=None, market_config=None):
    """Show current account status (uses injected broker or legacy Alpaca)."""
    currency_sym = market_config.currency_symbol if market_config else "$"
    market_name = market_config.market_name if market_config else "US Stocks"

    # ── Use injected broker when available ──
    if broker is not None:
        try:
            acct = broker.get_account()
            ms = calendar.status_str() if calendar else "?"

            print("\n" + "=" * 50)
            print(f"  {market_name.upper()} ACCOUNT")
            print("=" * 50)
            print(f"  Buying Power:  {currency_sym}{acct.buying_power:,.0f}")
            print(f"  Cash:          {currency_sym}{acct.cash:,.0f}")
            print(f"  Portfolio:     {currency_sym}{acct.portfolio_value:,.0f}")
            print(f"  Currency:      {acct.currency}")
            print(f"  Market:        {ms}")

            positions = broker.get_positions()
            if positions:
                print(f"\n  Positions ({len(positions)}):")
                for p in positions[:20]:
                    sym = p.symbol if hasattr(p, 'symbol') else p.get('symbol', '?')
                    qty = p.qty if hasattr(p, 'qty') else p.get('qty', 0)
                    mv = p.market_value if hasattr(p, 'market_value') else p.get('market_value', 0)
                    price = p.current_price if hasattr(p, 'current_price') else p.get('current_price', 0)
                    print(f"    {sym:<10} {float(qty):>8.0f} sh  @ {currency_sym}{float(price):.2f}  = {currency_sym}{float(mv):>10,.0f}")
                if len(positions) > 20:
                    print(f"    ... and {len(positions) - 20} more")
            else:
                print("\n  No open positions.")
            print("=" * 50)
            return
        except Exception as e:
            print(f"  Broker account fetch failed: {e}")

    # ── Legacy Alpaca fallback ──
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


def print_memory_summary():
    """Print memory system summary."""
    if not _memory_client:
        return
    try:
        stats = _memory_client.get_statistics()
        total = stats.get("total_memories", 0)
        if total > 0:
            print(f"\n  [Memory] {total} total memories stored")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="LIANGHUA Paper Trading System")

    parser.add_argument(
        "--mode", choices=["backtest", "once", "continuous"], default="backtest",
        help="backtest=historical simulation | once=single live cycle | continuous=auto-trading loop",
    )

    # Universe vs explicit symbols
    parser.add_argument(
        "--universe", type=str, default=None,
        choices=["nasdaq100", "sp500", "liquid", "all",
                 "csi300", "csi500", "liquid_cn", "all_cn"],
        help="Auto-fetch tradeable stocks. US: nasdaq100/sp500/liquid/all. CN: csi300/csi500/liquid_cn/all_cn.",
    )
    parser.add_argument(
        "--market", type=str, default="us", choices=["us", "cn"],
        help="Market: us (Alpaca, USD) or cn (A-Share, CNY).",
    )
    parser.add_argument(
        "--broker", type=str, default="paper", choices=["paper", "emt", "alpaca"],
        help="Broker: paper (simulation) | emt (东方财富 EMT real API) | alpaca (Alpaca real trading).",
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
        "--max-universe", type=int, default=200,
        help="Maximum number of symbols in universe (pre-screened for CN, capped for US).",
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
        "--max-market-cap", type=float, default=None,
        help="Maximum market cap in 亿元 (e.g. 500 = ¥500亿). Filters to small/mid-cap only. "
             "For US stocks, converted to USD (1 亿 ≈ $14M).",
    )
    parser.add_argument(
        "--rolling", action="store_true",
        help="Use rolling weekly inference in backtest mode.",
    )
    parser.add_argument(
        "--no-rag", action="store_true",
        help="Disable RAG knowledge base queries.",
    )
    parser.add_argument(
        "--no-memory", action="store_true",
        help="Disable Neo4j memory storage/retrieval.",
    )

    args = parser.parse_args()
    symbols = resolve_symbols(args)

    # Auto-detect market from universe choice
    cn_scopes = {"csi300", "csi500", "liquid_cn", "all_cn"}
    if args.universe and args.universe in cn_scopes:
        args.market = "cn"

    rag_enabled = not args.no_rag
    memory_enabled = not args.no_memory

    # ── Market components ──
    market_config, data_provider, broker, calendar = _create_market_components(
        args.market, args.capital, broker_type=args.broker
    )

    print_banner(args, symbols, rag_enabled, memory_enabled, market_config)

    # ── Init RAG ──
    rag_summary = ""
    if rag_enabled:
        print("\n  [RAG] Initializing knowledge base ...")
        if _init_rag(enable=True):
            print("  [RAG] Querying Alpha101 paper for relevant research ...")
            rag_summary = _build_rag_summary(args.mode, len(symbols))
            if rag_summary:
                print(f"\n{rag_summary}")
            else:
                print("  [RAG] No relevant results found.")
        else:
            print("  [RAG] Unavailable - continuing without knowledge base.")

    # ── Init Memory ──
    if memory_enabled:
        print("\n  [Memory] Initializing Neo4j ...")
        if _init_memory(enable=True):
            print("  [Memory] Connected - querying past lessons ...")
            lessons = _memory_lessons("strategy")
            if lessons:
                print(f"  [Memory] Found {len(lessons)} past lessons:")
                for l in lessons[:3]:
                    print(f"    - {l[:120]}...")
            else:
                print("  [Memory] No past lessons found - starting fresh.")
        else:
            print("  [Memory] Unavailable - continuing without memory.")

    # ── Init Orchestrator (with injected market components) ──
    print("\n  Initializing orchestrator (Alpha + Risk + Portfolio + Backtest + Execution) ...")
    orch = Orchestrator(
        data_provider=data_provider,
        broker=broker,
        market_config=market_config,
        market_calendar=calendar,
    )
    print("  Ready.\n")

    # Show account for live modes
    if args.mode in ("once", "continuous"):
        show_account(broker=broker, calendar=calendar, market_config=market_config)

    # ═══════════════════════════════════════════════════════════════
    # Execute
    # ═══════════════════════════════════════════════════════════════

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

        # Store reflections based on backtest outcome
        if memory_enabled:
            _store_pipeline_reflections("backtest", result, len(symbols))

    elif args.mode == "once":
        result = orch.run_live_trading_cycle(
            symbols=symbols,
            total_capital=args.capital,
            max_positions=args.max_positions,
        )
        print_once_result(result)

        if memory_enabled:
            _store_pipeline_reflections("live_once", result, len(symbols))

    elif args.mode == "continuous":
        orch.run_live_trading_loop(
            symbols=symbols,
            total_capital=args.capital,
            interval_seconds=args.interval,
            max_positions=args.max_positions,
        )

    # ── Final summary ──
    print_memory_summary()
    _close_memory()


if __name__ == "__main__":
    main()
