
import os
import sys
import json
import time
import importlib
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import inspect
from typing import Any, Dict, Optional, Callable, List, Union

current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent_pools.poe_config import setup_poe_env, resolve_poe_model
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

setup_poe_env()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Orchestrator")

# Add agent paths to sys.path
agent_pools_dir = project_root / "agent_pools"

if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import Agents
try:
    from agent_pools.alpha_agent_demo.alpha_signal_agent import AlphaSignalAgent
    from agent_pools.risk_agent_demo.risk_signal_agent import RiskSignalAgent
    from agent_pools.portfolio_agent_demo.portfolio_agent import PortfolioAgent
    from agent_pools.execution_agent_demo.execution_agent_demo.execution_agent import ExecutionAgent
    from agent_pools.backtest_agent_pool.backtest_agent import BacktestAgent
    from agent_pools.execution_agent_demo.execution_agent_demo.execution_agent import (
        is_market_open as _legacy_is_market_open,
        market_status_str as _legacy_market_status_str,
        alpaca_service as _legacy_alpaca_service,
    )
    from agent_pools.execution_agent_demo.execution_agent_demo.trade_journal import TradeJournal
    from agent_pools.portfolio_agent_demo.portfolio_agent import generate_orders
except ImportError as e:
    logger.error(f"Failed to import agents: {e}")
    sys.exit(1)

# Import Local Agents SDK
try:
    from agent_pools.alpha_agent_pool.local_agents import Agent, function_tool
except ImportError as e:
    logger.error(f"Local agents sdk not found. {e}")
    sys.exit(1)

# New abstractions (optional — graceful fallback if not installed)
try:
    from market import MarketConfig, US_MARKET, USMarketCalendar
    from data.providers import DataProvider
    from broker import Broker
    _NEW_ABSTRACTIONS = True
except ImportError:
    logger.warning("New market abstractions not found. Using legacy US-only mode.")
    _NEW_ABSTRACTIONS = False
    MarketConfig = None
    US_MARKET = None
    USMarketCalendar = None
    DataProvider = None
    Broker = None

# ------------------------------------------------------------------------------
# Data Client (legacy — used only when no DataProvider is injected)
# ------------------------------------------------------------------------------
try:
    StockHistoricalDataClient = importlib.import_module("alpaca.data.historical").StockHistoricalDataClient
    StockBarsRequest = importlib.import_module("alpaca.data.requests").StockBarsRequest
    StockLatestQuoteRequest = importlib.import_module("alpaca.data.requests").StockLatestQuoteRequest
    TimeFrame = importlib.import_module("alpaca.data.timeframe").TimeFrame
except ImportError:
    logger.warning("alpaca-py not installed. Data fetching will be mocked.")
    StockHistoricalDataClient = None
    StockLatestQuoteRequest = None

# ------------------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------------------
class Orchestrator:
    def __init__(
        self,
        data_provider=None,       # DataProvider instance (optional)
        broker=None,               # Broker instance (optional)
        market_config=None,        # MarketConfig instance (optional)
        market_calendar=None,      # MarketCalendar instance (optional)
    ):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.poe_model = resolve_poe_model("GPT-5.4")

        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not found. Agents might fail.")

        # ── Market abstractions ────────────────────────────────
        if _NEW_ABSTRACTIONS:
            self.market_config = market_config or US_MARKET
            if market_calendar is not None:
                self.calendar = market_calendar
            else:
                self.calendar = USMarketCalendar()
            self.data_provider = data_provider
            self.broker = broker
            logger.info("Orchestrator using %s market (DataProvider=%s, Broker=%s)",
                        self.market_config.code,
                        type(self.data_provider).__name__ if self.data_provider else "legacy",
                        type(self.broker).__name__ if self.broker else "legacy")
        else:
            self.market_config = None
            self.calendar = None
            self.data_provider = None
            self.broker = None

        # ── Legacy data client (used when no DataProvider is injected) ──
        # Data Client
        if StockHistoricalDataClient and self.api_key:
            self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        else:
            self.data_client = None

        # ── Execution agent (always created — can use broker when available) ──
        self.execution_agent = ExecutionAgent(
            alpaca_api_key=self.api_key,
            alpaca_secret_key=self.secret_key,
            paper=True
        )
        # If broker is available, inject it into the execution agent
        if self.broker is not None:
            self.execution_agent._injected_broker = self.broker
            self.execution_agent._injected_calendar = self.calendar

        # ── Sub-Agents ─────────────────────────────────────────
        self.alpha_agent = AlphaSignalAgent(name="AlphaCore", model=self.poe_model)
        self.risk_agent = RiskSignalAgent(name="RiskCore", model=self.poe_model)
        self.portfolio_agent = PortfolioAgent(name="PortfolioCore", model=self.poe_model)
        self.backtest_agent = BacktestAgent()

        # ── News Sentiment Agent (optional) ──
        self.news_agent = None
        try:
            from agent_pools.news_agent import NewsSentimentAgent
            self.news_agent = NewsSentimentAgent()
            logger.info("News sentiment agent ready")
        except Exception as e:
            logger.info("News agent unavailable (%s)", e)

        # Pipeline Context (Shared Memory)
        self.pipeline_context = {}

        # ── Neo4j Memory Client (self-optimizing agent) ──
        self._memory_client = None
        try:
            from agent_pools.memory.agent_memory_client import AgentMemoryClient
            self._memory_client = AgentMemoryClient()
            logger.info("Memory system connected — agent will learn from past trades")
        except Exception as e:
            logger.info("Memory system unavailable (%s) — running without learning", e)

        # Initialize Manager with Agent-as-Tool pattern
        self._initialize_manager_agent()

    # ═══════════════════════════════════════════════════════════════
    # News Sentiment Blending
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _blend_news_sentiment(alpha_result: Dict, news_sentiment: Dict) -> Dict:
        """
        Blend news sentiment into alpha signals: 80% alpha + 20% news.

        News sentiment [-1, 1] is scaled to match alpha signal range and added
        as a modifier. This gives news a meaningful but bounded influence on
        the final signal.
        """
        signals = alpha_result.get("signals", {})
        if not signals or not news_sentiment:
            return alpha_result

        blended = dict(signals)
        news_weight = 0.20  # 20% news influence

        for key, alpha_score in signals.items():
            # Extract symbol from key (handles both tuple and string keys)
            if isinstance(key, tuple):
                sym = key[1] if len(key) > 1 else key[0]
            else:
                sym = str(key)

            news_score = news_sentiment.get(sym, 0.0)
            if news_score != 0.0:
                # Blend: 80% alpha + 20% news (news_scaled to similar range)
                blended[key] = alpha_score * (1 - news_weight) + news_score * 0.5 * news_weight

        alpha_result["signals"] = blended
        alpha_result["news_blended"] = True
        return alpha_result

    # ═══════════════════════════════════════════════════════════════
    # Memory Helpers (Agent Self-Optimization)
    # ═══════════════════════════════════════════════════════════════

    def _recall_lessons(self, keywords: List[str]) -> List[str]:
        """Query Neo4j for past lessons relevant to current context."""
        if not self._memory_client:
            return []
        lessons = []
        for kw in keywords:
            try:
                result = self._memory_client.retrieve_lessons_by_issue(kw)
                if result:
                    lessons.extend(result)
            except Exception:
                pass
        return list(set(lessons))  # deduplicate

    def _learn_from_cycle(self, strategy: str, outcome: str, metrics: Dict[str, Any]):
        """Store a lesson from the current trading cycle into Neo4j memory."""
        if not self._memory_client:
            return
        try:
            sharpe = metrics.get('sharpe_ratio', 0)
            ret = metrics.get('total_return', 0)
            mdd = metrics.get('max_drawdown', 0)
            regime = metrics.get('market_regime', 'unknown')
            n_stocks = metrics.get('n_symbols', 0)

            if sharpe > 1.0:
                self._memory_client.store_reflection(
                    agent_name="Orchestrator",
                    strategy_name=strategy,
                    issue=f"strong_performance_{regime}",
                    lesson_learned=(
                        f"Sharpe={sharpe:.2f} Return={ret:.2%} MDD={mdd:.2%} "
                        f"on {n_stocks} stocks in {regime} regime. "
                        f"Strategy works well in this market condition."
                    ),
                )
            elif sharpe < -0.5:
                self._memory_client.store_reflection(
                    agent_name="Orchestrator",
                    strategy_name=strategy,
                    issue=f"poor_performance_{regime}",
                    lesson_learned=(
                        f"Sharpe={sharpe:.2f} Return={ret:.2%} MDD={mdd:.2%} "
                        f"on {n_stocks} stocks in {regime} regime. "
                        f"Consider reducing position size or switching factors."
                    ),
                )

            if mdd < -0.05:
                self._memory_client.store_reflection(
                    agent_name="Orchestrator",
                    strategy_name=strategy,
                    issue="large_drawdown",
                    lesson_learned=(
                        f"MaxDrawdown={mdd:.2%} with Sharpe={sharpe:.2f}. "
                        f"Add tighter stop-loss or reduce max positions below "
                        f"{n_stocks} in {regime} conditions."
                    ),
                )

            logger.info("Memory: stored %d lessons from this cycle", 3 if sharpe > 1 else 2 if mdd < -0.05 else 1)
        except Exception as e:
            logger.debug("Memory store failed (non-critical): %s", e)

    def _patch_agent_to_support_as_tool(self, agent_instance):
        """
        Monkey-patch the agent instance to support 'as_tool' 
        if it was initialized with the fallback Agent class.
        """
        if not hasattr(agent_instance, 'as_tool'):
            # Bind the as_tool method from our local Agent class to this instance
            import types
            agent_instance.as_tool = types.MethodType(Agent.as_tool, agent_instance)

    def _initialize_manager_agent(self):
        """Initialize the Manager Agent using the Agent-as-Tool pattern"""
        
        # 1. Prepare Sub-Agents
        # We need to patch them because they might be using the minimal Agent class from their own files
        self._patch_agent_to_support_as_tool(self.alpha_agent.agent)
        self._patch_agent_to_support_as_tool(self.risk_agent.agent)
        self._patch_agent_to_support_as_tool(self.portfolio_agent.agent)
        self._patch_agent_to_support_as_tool(self.execution_agent.agent)
        self._patch_agent_to_support_as_tool(self.backtest_agent) # BacktestAgent inherits from Agent
        
        # 2. Define Helper Tools (Hosted Tools Equivalent)
        @function_tool
        def fetch_market_data(symbol: str, start_date: str, end_date: str) -> str:
            """Fetch and store market data in shared context."""
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                data = self.fetch_data(symbol, start_dt, end_dt)
                
                self.pipeline_context['market_data'] = data
                self.pipeline_context['symbol'] = symbol
                self.pipeline_context['dates'] = (start_date, end_date)
                
                return f"Data fetched for {symbol}. stored in context."
            except Exception as e:
                return f"Error: {e}"

        @function_tool
        def store_reflection(strategy_name: str, issue: str, lesson: str) -> str:
            """Store a learned lesson into Neo4j long-term memory for future reference."""
            try:
                from agent_pools.memory.agent_memory_client import AgentMemoryClient
                client = AgentMemoryClient()
                result = client.store_reflection(
                    agent_name="Orchestrator", strategy_name=strategy_name,
                    issue=issue, lesson_learned=lesson)
                client.close()
                return result
            except Exception as e:
                return f"Memory store skipped (Neo4j not available): {e}"

        @function_tool
        def query_lessons(keyword: str) -> str:
            """Query past lessons from Neo4j memory. Use keywords like 'overfitting', 'momentum', 'risk'."""
            try:
                from agent_pools.memory.agent_memory_client import AgentMemoryClient
                client = AgentMemoryClient()
                lessons = client.retrieve_lessons_by_issue(keyword)
                client.close()
                if not lessons:
                    return f"No past lessons found for '{keyword}'."
                return "Past lessons:\n" + "\n".join(lessons)
            except Exception as e:
                return f"Memory query skipped (Neo4j not available): {e}"

        @function_tool
        def search_knowledge(query: str, top_k: int = 3) -> str:
            """Search the Alpha101 research paper (RAG) for relevant factor construction knowledge."""
            try:
                from agent_pools.memory.agent_rag_client import get_rag_client
                rag = get_rag_client()
                results = rag.query(query, n_results=top_k)
                if not results:
                    return "No matching research found in the knowledge base."
                return f"Found {len(results)} relevant passages:\n\n" + "\n\n".join(results)
            except Exception as e:
                return f"RAG search skipped: {e}"

        # 3. Create Manager Agent with Agents as Tools
        # This matches the "Agent as Tool" pattern from the docs
        
        self.manager_agent = Agent(
            name="OrchestratorAgent",
            instructions=(
                "You are a trading strategy manager. You use the tools given to you to execute the pipeline. "
                "1. Fetch data first. "
                "2. Search knowledge base (search_knowledge) for relevant factor research before analyzing. "
                "3. Ask Alpha Agent to analyze. "
                "4. Ask Risk Agent to assess. "
                "5. Ask Portfolio Agent to construct portfolio. "
                "6. Ask Execution Agent to trade OR Backtest Agent to simulate. "
                "7. Store important lessons learned (store_reflection) to memory for future reference."
            ),
            tools=[
                # Helper Tools
                fetch_market_data,
                store_reflection,
                query_lessons,
                search_knowledge,
                
                # Agents as Tools
                self.alpha_agent.agent.as_tool(
                    tool_name="ask_alpha_agent",
                    tool_description="Ask Alpha Agent to generate signals. Requires market data."
                ),
                self.risk_agent.agent.as_tool(
                    tool_name="ask_risk_agent",
                    tool_description="Ask Risk Agent to assess market risks."
                ),
                self.portfolio_agent.agent.as_tool(
                    tool_name="ask_portfolio_agent",
                    tool_description="Ask Portfolio Agent to generate target weights."
                ),
                self.execution_agent.agent.as_tool(
                    tool_name="ask_execution_agent",
                    tool_description="Ask Execution Agent to execute trades."
                ),
                self.backtest_agent.as_tool(
                    tool_name="ask_backtest_agent",
                    tool_description="Ask Backtest Agent to run simulation."
                )
            ]
        )

    def fetch_data(self, symbols: Union[str, List[str]], start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch historical data — delegates to DataProvider if available, else Alpaca/Mock."""
        if isinstance(symbols, str):
            symbols = [symbols]

        logger.info(f"Fetching data for {symbols} from {start_date.date()} to {end_date.date()}")

        # ── Use DataProvider when available ──
        if self.data_provider is not None:
            try:
                df = self.data_provider.get_historical_bars(symbols, start_date, end_date)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning("DataProvider.get_historical_bars failed: %s — falling back to legacy", e)

        # ── Legacy path (Alpaca → yfinance → mock) ──
        if self.data_client:
            try:
                request_params = StockBarsRequest(
                    symbol_or_symbols=symbols,
                    timeframe=TimeFrame.Day,
                    start=start_date,
                    end=end_date
                )
                bars = self.data_client.get_stock_bars(request_params)
                df = bars.df.reset_index()
                df = df.rename(columns={'timestamp': 'date'})
                df['date'] = df['date'].dt.tz_localize(None)
                return df
            except Exception as e:
                logger.error(f"Alpaca data fetch failed: {e}. Using fallback.")
        
        # Try YFinance (Real Data Fallback)
        try:
            import yfinance as yf
            import logging
            # Suppress yfinance noise
            logging.getLogger('yfinance').setLevel(logging.CRITICAL)
            
            all_dfs = []
            for symbol in symbols:
                # Fetch data
                try:
                    df = yf.download(symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
                    
                    if df.empty:
                        continue
                        
                    # Handle MultiIndex columns (yfinance > 0.2)
                    if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
                        # Single symbol: 'Close'/'AAPL' → 'Close'. Safe to droplevel.
                        df.columns = df.columns.droplevel(1)
                        # Safety: if droplevel created duplicates, use first level instead
                        if df.columns.duplicated().any():
                            df.columns = [str(c[0]).lower() for c in df.columns]
                            
                    df = df.reset_index()
                    # Standardize columns
                    df.columns = [str(c).lower() for c in df.columns]
                    
                    # Ensure 'date' column
                    if 'date' not in df.columns:
                        date_cols = [c for c in df.columns if 'date' in c]
                        if date_cols:
                            df = df.rename(columns={date_cols[0]: 'date'})
                    
                    # Keep only standard columns to ensure clean concat
                    required_cols = ['open', 'high', 'low', 'close', 'volume']
                    valid_cols = [c for c in required_cols if c in df.columns]
                    
                    if 'date' in df.columns:
                        df = df[['date'] + valid_cols].copy()
                        df['symbol'] = symbol
                        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
                        all_dfs.append(df)
                        
                except Exception as e:
                    logger.warning(f"Failed to process {symbol}: {e}")
                    continue
            
            if all_dfs:
                logger.info(f"✅ Successfully fetched real data via yfinance for {len(all_dfs)} symbols")
                return pd.concat(all_dfs, ignore_index=True)
                
        except ImportError:
            logger.warning("yfinance not installed. Falling back to mock data.")
        except Exception as e:
            logger.error(f"yfinance fetch failed: {e}")
        
        # Mock Data
        all_dfs = []
        dates = pd.date_range(start=start_date, end=end_date, freq='B')
        n = len(dates)
        
        for symbol in symbols:
            # Generate regime-switching price path to force signal changes
            # Include start_date in seed to ensure different data for different periods
            seed_val = (hash(symbol) + int(start_date.timestamp())) % (2**32)
            np.random.seed(seed_val)
            
            # Construct regimes
            p1 = n // 3
            p2 = n // 3
            p3 = n - p1 - p2
            
            # Regime 1: Bullish (Low Vol)
            r1 = np.random.normal(0.001, 0.01, p1)
            # Regime 2: Bearish (High Vol)
            r2 = np.random.normal(-0.0015, 0.02, p2)
            # Regime 3: Rebound (Med Vol)
            r3 = np.random.normal(0.0005, 0.015, p3)
            
            rets = np.concatenate([r1, r2, r3])
            price = 100.0 * np.cumprod(1 + rets)
            
            df = pd.DataFrame({
                'date': dates, 'symbol': symbol,
                'open': price, 'high': price*1.01, 'low': price*0.99, 'close': price,
                'volume': np.random.randint(1000, 10000, n)
            })
            all_dfs.append(df)
            
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

    def _quick_screen_live(
        self, symbols: List[str], top_n: int = 200
    ) -> List[str]:
        """
        Fast pre-screen for live trading: use Alpaca snapshots to filter the
        universe down to the top candidates by momentum + volume, so the ML
        pipeline only runs on a manageable subset.
        """
        if len(symbols) <= top_n:
            return symbols

        # ── Delegate to data provider when available ──
        if self.data_provider is not None and hasattr(self.data_provider, 'quick_screen'):
            try:
                return self.data_provider.quick_screen(symbols, top_n=top_n)
            except Exception as e:
                logger.warning("DataProvider.quick_screen failed: %s", e)

        # ── Legacy path ──
        if not self.data_client:
            logger.info("No Alpaca data client — using first %d symbols", top_n)
            return symbols[:top_n]

        try:
            from alpaca.data.requests import StockSnapshotRequest

            scored: List[tuple] = []  # (symbol, score)
            batch_size = 500

            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                try:
                    req = StockSnapshotRequest(symbol_or_symbols=batch)
                    snaps = self.data_client.get_stock_snapshot(req)

                    for sym, snap in (snaps or {}).items():
                        bar = getattr(snap, 'daily_bar', None)
                        prev_bar = getattr(snap, 'previous_daily_bar', None)
                        trade = getattr(snap, 'latest_trade', None)

                        price = 0.0
                        if trade and getattr(trade, 'price', 0):
                            price = float(trade.price)
                        elif bar and getattr(bar, 'close', 0):
                            price = float(bar.close)

                        volume = float(getattr(bar, 'volume', 0)) if bar else 0.0

                        # Skip ultra-low price / no-volume stocks
                        if price < 2 or volume < 50_000:
                            continue

                        # Simple momentum score: today's change % weighted by volume
                        prev_close = float(getattr(prev_bar, 'close', price)) if prev_bar else price
                        change_pct = (price - prev_close) / prev_close if prev_close > 0 else 0

                        # Score = abs(momentum) * log(volume)  (prefer high vol + strong move)
                        score = abs(change_pct) * np.log1p(volume)
                        scored.append((sym, score))

                except Exception as e:
                    logger.warning("Snapshot screen batch failed: %s", e)
                    # Keep a portion of the failed batch
                    scored.extend((s, 0) for s in batch[:50])

            # Sort by score descending, take top_n
            scored.sort(key=lambda x: x[1], reverse=True)
            selected = [s for s, _ in scored[:top_n]]

            logger.info("Quick screen: %d -> %d candidates (momentum+volume)", len(symbols), len(selected))
            return selected

        except Exception as e:
            logger.warning("Quick screen failed: %s — falling back to first %d", e, top_n)
            return symbols[:top_n]

    def fetch_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch real-time prices — delegates to DataProvider if available.
        Uses batched snapshot requests for efficiency with large symbol lists.
        """
        # ── Use DataProvider when available ──
        if self.data_provider is not None:
            try:
                return self.data_provider.get_realtime_prices(symbols)
            except Exception as e:
                logger.warning("DataProvider.get_realtime_prices failed: %s — falling back to legacy", e)

        # ── Legacy path ──
        prices: Dict[str, float] = {}

        # 1. Try Alpaca snapshots (batched, efficient for many symbols)
        if self.data_client:
            try:
                from alpaca.data.requests import StockSnapshotRequest

                for i in range(0, len(symbols), 500):
                    batch = symbols[i:i + 500]
                    req = StockSnapshotRequest(symbol_or_symbols=batch)
                    snaps = self.data_client.get_stock_snapshot(req)
                    for sym, snap in (snaps or {}).items():
                        trade = getattr(snap, 'latest_trade', None)
                        bar = getattr(snap, 'daily_bar', None)
                        p = 0.0
                        if trade and getattr(trade, 'price', 0):
                            p = float(trade.price)
                        elif bar and getattr(bar, 'close', 0):
                            p = float(bar.close)
                        if p > 0:
                            prices[sym] = p

                if prices:
                    logger.info("Real-time prices from Alpaca snapshots: %d symbols", len(prices))
                    return prices
            except Exception as e:
                logger.warning("Alpaca snapshot prices failed: %s", e)

        # 2. Mock fallback
        logger.warning("Using mock real-time prices ($100 each)")
        return {s: 100.0 for s in symbols}

    def run_pipeline(self, symbol: Union[str, List[str]], start_date: str, end_date: str, mode: str = "backtest",
                     total_capital: float = 100000.0, rebalance_freq: int = 5, max_positions: int = 20) -> Dict[str, Any]:
        """
        Run the complete investment pipeline: Data -> Alpha -> Risk -> Portfolio -> Backtest
        """
        # Handle both string and list of symbols
        symbols = [symbol] if isinstance(symbol, str) else symbol
        symbol_str = ", ".join(symbols)
        
        logger.info(f"Running pipeline for {len(symbols)} symbols from {start_date} to {end_date}")

        # 1. Data Fetching
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # ROLLING WINDOW: Fetch 1 year prior for training to avoid leakage
            lookback_days = 365
            fetch_start_dt = start_dt - timedelta(days=lookback_days)

            if len(symbols) > 50:
                print(f"\n  📊 Fetching data for {len(symbols)} symbols...")
            logger.info(f"Fetching extended data from {fetch_start_dt.date()} to {end_dt.date()} for Rolling Training...")
            
            full_data = self.fetch_data(symbols, fetch_start_dt, end_dt)
            
            if full_data.empty:
                return {"status": "error", "message": "No data fetched"}
            
            # Split into Train/Test
            if 'date' in full_data.columns:
                full_data['date'] = pd.to_datetime(full_data['date']).dt.tz_localize(None)
                train_data = full_data[full_data['date'] < start_dt].copy()
                test_data = full_data[full_data['date'] >= start_dt].copy()
                
                logger.info(f"Data Split - Train: {len(train_data)} rows ({fetch_start_dt.date()} to {start_dt.date()}), Test: {len(test_data)} rows ({start_dt.date()} to {end_dt.date()})")
            else:
                logger.warning("Date column missing. Using full data as test (Risk of Leakage).")
                train_data = None
                test_data = full_data

            # 1b. Memory recall — query past lessons for current context
            lessons = self._recall_lessons(["performance", "drawdown", "Sharpe", "regime", "factor", "strategy"])
            if lessons:
                logger.info("Memory: recalled %d past lessons for this cycle", len(lessons))
                self.pipeline_context['past_lessons'] = lessons

            # 1c. News sentiment — analyze recent news for candidate stocks
            news_sentiment = {}
            if self.news_agent and self.news_agent.is_available:
                try:
                    news_result = self.news_agent.analyze(symbols, lookback_days=3)
                    news_sentiment = news_result.get("sentiment", {})
                    self.pipeline_context['news_sentiment'] = news_sentiment
                    self.pipeline_context['news_narrative'] = news_result.get("narrative", "")
                    self.pipeline_context['news_sector_impact'] = news_result.get("sector_impact", {})
                    if news_sentiment:
                        logger.info("News: analyzed %d stocks, sentiment range [%.2f, %.2f]",
                                    len(news_sentiment),
                                    min(news_sentiment.values()),
                                    max(news_sentiment.values()))
                except Exception as e:
                    logger.debug("News analysis skipped: %s", e)

            # 2. Alpha Generation — Alpha158 factors + LightGBM by default
            alpha_result = self.alpha_agent.generate_signals_from_data(
                data=test_data,  # Predict on Test
                train_data=train_data,  # Train on History
            )

            # 2b. Blend news sentiment into alpha signals (20% news + 80% alpha)
            if news_sentiment and alpha_result.get("status") == "success":
                alpha_result = self._blend_news_sentiment(alpha_result, news_sentiment)
            
            if alpha_result["status"] != "success":
                return {"status": "error", "message": f"Alpha generation failed: {alpha_result.get('message')}"}
            
            # 3. Risk Analysis
            risk_result = self.risk_agent.generate_risk_signals_from_data(test_data)

            if risk_result["status"] != "success":
                logger.warning(f"Risk analysis failed: {risk_result.get('message')}")

            # 4. Portfolio Construction — extract per-symbol scores from alpha signals
            # Alpha signals format: {(date, symbol): score} — collate latest score per symbol
            predictions_dict = alpha_result.get("signals", {})
            if not predictions_dict:
                 return {"status": "error", "message": "No signals generated"}

            symbol_scores: Dict[str, float] = {}
            for key, score in predictions_dict.items():
                if isinstance(key, tuple):
                    sym = key[1] if len(key) > 1 else key[0]
                else:
                    sym = str(key)
                symbol_scores[sym] = float(score)

            portfolio_result = self.portfolio_agent.inference(
                alpha_signals=symbol_scores,
                risk_signals=risk_result,
                total_capital=total_capital,
                max_positions=max_positions,
                price_data=test_data,  # enables covariance optimization
            )

            if portfolio_result.get("status") != "success":
                logger.warning(f"Portfolio construction failed: {portfolio_result.get('message')}")

            # 5. Backtest — use the original MultiIndex signals for the backtest engine
            signals_series = pd.Series(predictions_dict)

            if not isinstance(signals_series.index, pd.MultiIndex):
                # Build proper MultiIndex to avoid silently dropping the second level name
                if len(symbols) == 1:
                    signals_series.index = pd.MultiIndex.from_product(
                        [signals_series.index, [symbols[0]]], names=['datetime', 'instrument'])
                else:
                    # Flat index with multiple symbols — rebuild as MultiIndex
                    signals_series.index = pd.MultiIndex.from_arrays(
                        [pd.Index([''] * len(signals_series)), signals_series.index],
                        names=['datetime', 'instrument'])
            else:
                signals_series.index.names = ['datetime', 'instrument']

            backtest_result = self.backtest_agent.run_simple_backtest_paper_interface(
                predictions=signals_series,
                start_time=start_date,
                end_time=end_date,
                investment_horizon=rebalance_freq,
                total_capital=total_capital,
                market_data=test_data,
                plot_results=False
            )

            # Attach portfolio & signal info for downstream execution
            backtest_result["signals"] = symbol_scores
            backtest_result["target_weights"] = portfolio_result.get("target_weights", {})
            backtest_result["risk_level"] = risk_result.get("overall_risk_level", "UNKNOWN")
            backtest_result["risk_score"] = risk_result.get("risk_score", 0.0)
            backtest_result["market_regime"] = risk_result.get("market_regime", "unknown")
            backtest_result["risk_narrative"] = risk_result.get("risk_narrative", "")
            backtest_result["exit_candidates"] = portfolio_result.get("exit_candidates", [])
            backtest_result["news_narrative"] = self.pipeline_context.get("news_narrative", "")
            backtest_result["news_sector_impact"] = self.pipeline_context.get("news_sector_impact", {})

            # 6. Memory: store lessons from this cycle for future self-optimization
            self._learn_from_cycle(
                strategy=f"{mode}_pipeline",
                outcome="success" if backtest_result.get("status") != "error" else "error",
                metrics={
                    "sharpe_ratio": backtest_result.get("performance_metrics", {}).get("sharpe_ratio", 0),
                    "total_return": backtest_result.get("performance_metrics", {}).get("total_return", 0),
                    "max_drawdown": backtest_result.get("performance_metrics", {}).get("max_drawdown", 0),
                    "market_regime": risk_result.get("market_regime", "unknown"),
                    "n_symbols": len(symbols),
                },
            )

            return backtest_result
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def run_inference_rolling_week(self, symbol: Union[str, List[str]], start_date: str, end_date: str, 
                                  lookback_days: int = 365, rebalance_freq: int = 5, total_capital: float = 100000.0) -> Dict[str, Any]:
        """
        Run inference in a strict 'World Model' fashion (Rolling Week):
        - Incrementally reveal data week by week.
        - Retrain/Predict for the upcoming week.
        - Simulate weekly rebalancing.
        """
        symbols = [symbol] if isinstance(symbol, str) else symbol
        logger.info(f"🚀 Starting World Model Inference (Rolling Week) for {symbols} ({start_date} to {end_date})")

        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

            # 1. Fetch All Data
            fetch_start = start_dt - timedelta(days=lookback_days)
            full_data = self.fetch_data(symbols, fetch_start, end_dt)

            if full_data.empty or 'date' not in full_data.columns:
                return {"status": "error", "message": "Data fetch failed"}

            full_data['date'] = pd.to_datetime(full_data['date']).dt.tz_localize(None)

            # 1b. Pre-compute Alpha158 features ONCE for the entire dataset.
            #     Rolling-window factors only look BACKWARD, so no leakage.
            #     This avoids 52x redundant recomputation in the weekly loop.
            logger.info("Pre-computing Alpha158 features on full dataset (%d rows)...", len(full_data))
            from agent_pools.alpha_agent_demo.alpha158_calculator import Alpha158Calculator
            from agent_pools.alpha_agent_demo.alpha_signal_agent import _preprocess_features

            calc = Alpha158Calculator()
            all_features = calc.compute(full_data)
            all_features = _preprocess_features(all_features)
            all_features['_date'] = full_data['date'].values
            all_features['_symbol'] = full_data['symbol'].values if 'symbol' in full_data.columns else '_all'
            logger.info("Features computed: %d factors x %d rows", all_features.shape[1] - 2, len(all_features))

            # 2. Weekly Loop — slice pre-computed features, don't recompute
            current_dt = start_dt
            all_signals_list = []

            while current_dt < end_dt:
                next_week_dt = current_dt + timedelta(weeks=1)
                if next_week_dt > end_dt:
                    next_week_dt = end_dt

                train_start = current_dt - timedelta(days=lookback_days)

                # Slice pre-computed features by date
                train_mask = (all_features['_date'] >= train_start) & (all_features['_date'] < current_dt)
                test_mask = (all_features['_date'] >= current_dt) & (all_features['_date'] < next_week_dt)

                if test_mask.sum() == 0:
                    current_dt = next_week_dt
                    continue

                logger.info(f"📅 Rolling Step: {current_dt.date()} -> {next_week_dt.date()} "
                           f"(Train: {train_mask.sum()}, Test: {test_mask.sum()})")

                # Compute target (forward return) per-window to avoid leakage
                train_data_slice = full_data[train_mask].copy()
                test_data_slice = full_data[test_mask].copy()

                if 'symbol' in train_data_slice.columns:
                    y_train = train_data_slice.groupby('symbol')['close'].pct_change().shift(-1)
                else:
                    y_train = train_data_slice['close'].pct_change().shift(-1)

                # Drop metadata columns for model input
                feature_cols = [c for c in all_features.columns if c not in ('_date', '_symbol')]
                X_train = all_features.loc[train_mask, feature_cols].copy()
                X_test = all_features.loc[test_mask, feature_cols].copy()

                # Align and train
                try:
                    from agent_pools.alpha_agent_demo.alpha_signal_agent import _train_model_and_predict
                    model_res = _train_model_and_predict(X_train, y_train, X_test, 'ensemble')

                    if model_res['status'] == 'success':
                        preds = pd.Series(model_res['predictions'], index=test_data_slice.index)
                        # Cross-sectional rank within this week
                        dates = test_data_slice['date'].values if 'date' in test_data_slice.columns else None
                        pred_df = pd.DataFrame({'pred': preds})
                        if dates is not None:
                            pred_df['_d'] = dates
                            pred_df['signal'] = pred_df.groupby('_d')['pred'].rank(pct=True) - 0.5
                        else:
                            pred_df['signal'] = pred_df['pred'].rank(pct=True) - 0.5

                        # Build MultiIndex output
                        sig_series = pred_df['signal']
                        if 'date' in test_data_slice.columns and 'symbol' in test_data_slice.columns:
                            sig_series.index = pd.MultiIndex.from_frame(
                                test_data_slice[['date', 'symbol']].reset_index(drop=True))
                        all_signals_list.append(sig_series)
                except Exception as e:
                    logger.warning(f"Rolling step model failed: {e}")

                # Step Forward
                current_dt = next_week_dt
                
            # 3. Aggregate & Backtest
            if not all_signals_list:
                return {"status": "error", "message": "No signals generated during rolling inference"}
                
            # Concat all weekly signal series
            full_signals_series = pd.concat(all_signals_list)
            
            # Ensure MultiIndex
            if not isinstance(full_signals_series.index, pd.MultiIndex):
                 if len(symbols) == 1:
                     full_signals_series.index = pd.MultiIndex.from_product([full_signals_series.index, [symbols[0]]], names=['datetime', 'instrument'])
                 else:
                     full_signals_series.index = pd.MultiIndex.from_arrays(
                         [pd.Index([''] * len(full_signals_series)), full_signals_series.index],
                         names=['datetime', 'instrument'])
            else:
                 full_signals_series.index.names = ['datetime', 'instrument']

            # Filter market_data to start_date -> end_date
            backtest_market_data = full_data[full_data['date'] >= start_dt].copy()

            backtest_result = self.backtest_agent.run_simple_backtest_paper_interface(
                predictions=full_signals_series,
                start_time=start_date,
                end_time=end_date,
                investment_horizon=rebalance_freq,
                total_capital=total_capital,
                market_data=backtest_market_data,
                plot_results=False
            )

            # Risk assessment on the full test period for reporting
            try:
                risk_result = self.risk_agent.generate_risk_signals_from_data(backtest_market_data, enable_llm=False)
                backtest_result["risk_level"] = risk_result.get("overall_risk_level", "UNKNOWN")
                backtest_result["risk_score"] = risk_result.get("risk_score", 0.0)
                backtest_result["market_regime"] = risk_result.get("market_regime", "unknown")
            except Exception as e:
                logger.warning("Rolling pipeline risk assessment failed: %s", e)
                backtest_result["risk_level"] = "UNKNOWN"

            # Attach the last week's signals for execution
            if all_signals_list:
                last_sigs = all_signals_list[-1]
                backtest_result["signals"] = last_sigs.to_dict() if hasattr(last_sigs, 'to_dict') else last_sigs

            return backtest_result
            
        except Exception as e:
            logger.error(f"Rolling inference error: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # ══════════════════════════════════════════════════════════════════════
    # Order Execution Helpers
    # ══════════════════════════════════════════════════════════════════════

    def _execute_via_broker(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute orders directly via the injected broker (bypasses legacy execution agent)."""
        results = []
        # Sort: sells first (T+1: free up locked shares before buying)
        sells = [o for o in orders if o["side"] == "sell"]
        buys = [o for o in orders if o["side"] == "buy"]

        for order in sells + buys:
            try:
                result = self.broker.place_order(
                    symbol=order["symbol"],
                    qty=order["qty"],
                    side=order["side"],
                    order_type=order.get("order_type", "market"),
                    limit_price=order.get("limit_price"),
                )
                results.append({
                    "symbol": result.symbol,
                    "status": result.status,
                    "qty": result.qty,
                    "side": result.side,
                    "filled_price": result.filled_price,
                    "error": result.error or "",
                })
            except Exception as e:
                logger.error("Broker order failed for %s: %s", order.get("symbol"), e)
                results.append({
                    "symbol": order.get("symbol", "?"),
                    "status": "failed",
                    "qty": order.get("qty", 0),
                    "side": order.get("side", "?"),
                    "error": str(e),
                })

        return results

    # ══════════════════════════════════════════════════════════════════════
    # Live Trading
    # ══════════════════════════════════════════════════════════════════════

    def run_live_trading_cycle(
        self,
        symbols: List[str],
        total_capital: float = 100000.0,
        max_positions: int = 20,
        journal=None,
    ) -> Dict[str, Any]:
        """
        Execute one complete trading cycle:
        Screen → Fetch → Alpha → Risk → Portfolio → Execute.

        For large universes (>200 symbols), a quick snapshot-based screen
        narrows the list before the full ML pipeline runs.
        """
        cycle_id = getattr(journal, '_cycle_id', 0) + 1 if journal else 0
        logger.info("=== Live Trading Cycle #%d ===", cycle_id)

        # ── Market status (use injected calendar or legacy) ──
        if self.calendar is not None:
            market_status = self.calendar.status_str()
            market_open = self.calendar.is_open()
        else:
            market_status = _legacy_market_status_str()
            market_open = _legacy_is_market_open()

        if journal:
            journal.start_cycle(cycle_id, market_status)

        if not market_open:
            logger.info("Market %s - skipping execution.", market_status)
            if journal:
                journal.finish_cycle()
            return {"status": "skipped", "market_status": market_status,
                    "reason": f"Market {market_status}", "cycle_id": cycle_id}

        try:
            # 0. Quick pre-screen for large universes (momentum + volume filter)
            candidates = self._quick_screen_live(symbols, top_n=200)
            logger.info("Live cycle: %d candidates after pre-screen (from %d total)",
                        len(candidates), len(symbols))

            # ── Get positions from injected broker or legacy Alpaca ──
            held_symbols = []
            if self.broker is not None:
                try:
                    for p in self.broker.get_positions():
                        s = p.symbol if hasattr(p, 'symbol') else p.get('symbol', '')
                        if s and s not in candidates:
                            held_symbols.append(s)
                except Exception as e:
                    logger.warning("Broker.get_positions failed: %s", e)
            elif _legacy_alpaca_service:
                try:
                    for p in _legacy_alpaca_service.get_positions():
                        s = getattr(p, "symbol", "")
                        if s and s not in candidates:
                            held_symbols.append(s)
                except Exception:
                    pass
            fetch_symbols = list(dict.fromkeys(candidates + held_symbols))  # dedupe, preserve order

            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=90)
            data = self.fetch_data(fetch_symbols, start_dt, end_dt)

            if data.empty:
                return {"status": "error", "message": "No market data", "cycle_id": cycle_id}

            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date']).dt.tz_localize(None)
                cutoff = data['date'].max() - timedelta(days=30)
                train_data = data[data['date'] < cutoff].copy()
                test_data = data[data['date'] >= cutoff].copy()
            else:
                train_data = data.iloc[:-30] if len(data) > 30 else data
                test_data = data.iloc[-30:] if len(data) > 30 else data

            # 1b. Memory recall
            lessons = self._recall_lessons(["performance", "drawdown", "Sharpe", "regime", "factor", "strategy"])
            if lessons:
                logger.info("Memory: recalled %d past lessons for live cycle", len(lessons))

            # 2. Alpha signals — Alpha158 factors + LightGBM by default
            alpha_result = self.alpha_agent.generate_signals_from_data(
                data=test_data, train_data=train_data,
            )

            if alpha_result["status"] != "success":
                return {"status": "error", "message": f"Alpha failed: {alpha_result.get('message')}", "cycle_id": cycle_id}

            # 3. Risk assessment (on candidates only for performance)
            risk_result = self.risk_agent.generate_risk_signals_from_data(test_data)

            # 4. Extract per-symbol scores from alpha signals
            predictions_dict = alpha_result.get("signals", {})
            symbol_scores: Dict[str, float] = {}
            for key, score in predictions_dict.items():
                sym = key[1] if isinstance(key, tuple) and len(key) > 1 else str(key)
                symbol_scores[sym] = float(score)

            # 5. Portfolio construction
            portfolio_result = self.portfolio_agent.inference(
                alpha_signals=symbol_scores,
                risk_signals=risk_result,
                total_capital=total_capital,
                max_positions=max_positions,
                price_data=test_data,  # enables covariance optimization
            )

            target_weights = portfolio_result.get("target_weights", {})
            risk_level = risk_result.get("overall_risk_level", "UNKNOWN")

            if journal:
                journal.log_signals(symbol_scores, risk_level)

            # 6. Get current positions from broker (injected or legacy)
            current_positions: Dict[str, float] = {}
            if self.broker is not None:
                try:
                    for p in self.broker.get_positions():
                        sym = p.symbol if hasattr(p, 'symbol') else p.get('symbol', '')
                        mv = p.market_value if hasattr(p, 'market_value') else p.get('market_value', 0)
                        if sym:
                            current_positions[sym] = float(mv)
                    logger.info("Current positions: %d held", len(current_positions))
                except Exception as e:
                    logger.warning("Failed to get broker positions: %s", e)
            elif _legacy_alpaca_service:
                try:
                    for p in _legacy_alpaca_service.get_positions():
                        sym = getattr(p, "symbol", "")
                        if sym:
                            current_positions[sym] = float(getattr(p, "market_value", 0))
                    logger.info("Current positions: %d held", len(current_positions))
                except Exception as e:
                    logger.warning("Failed to get Alpaca positions: %s", e)

            # 7. Real-time prices (only for symbols in target_weights + current positions)
            all_active = list(set(list(target_weights.keys()) + list(current_positions.keys())))
            market_prices = self.fetch_realtime_prices(all_active) if all_active else {}

            # 7.5 Update broker with latest market prices (for price limit checks)
            if self.broker is not None and hasattr(self.broker, 'update_market_prices'):
                try:
                    self.broker.update_market_prices(market_prices)
                except Exception:
                    pass

            # 8. Generate orders from weight diffs
            # Use CN order generation (lot sizing) when in A-share mode
            if self.market_config and self.market_config.code == "cn":
                from agent_pools.portfolio_agent_demo.portfolio_agent import generate_orders_cn
                orders = generate_orders_cn(
                    target_weights=target_weights,
                    current_positions=current_positions,
                    total_capital=total_capital,
                    market_prices=market_prices,
                    lot_size=self.market_config.lot_size,
                )
            else:
                orders = generate_orders(
                    target_weights=target_weights,
                    current_positions=current_positions,
                    total_capital=total_capital,
                    market_prices=market_prices,
                )

            decisions = [
                {"symbol": o["symbol"], "action": o["side"].upper(), "qty": o["qty"],
                 "reason": o.get("reason", "")}
                for o in orders
            ]
            if journal:
                journal.log_decisions(decisions)

            # 9. Execute orders — use injected broker when available, else legacy
            execution_results: List[Dict[str, Any]] = []
            if orders:
                if self.broker is not None:
                    # ── Use injected broker directly ──
                    execution_results = self._execute_via_broker(orders)
                else:
                    # ── Legacy execution agent path ──
                    execution_results = self.execution_agent.execute_orders_direct(orders)
                logger.info("Executed %d orders: %s", len(execution_results),
                            [(r.get("symbol"), r.get("status")) for r in execution_results])

                if journal:
                    for i, order in enumerate(orders):
                        result = execution_results[i] if i < len(execution_results) else {"status": "unknown"}
                        journal.log_execution(order, result)

            if journal:
                journal.finish_cycle()

            # Memory: store lessons from this live cycle
            self._learn_from_cycle(
                strategy="live_trading",
                outcome="success",
                metrics={
                    "sharpe_ratio": 0,  # live cycle doesn't compute sharpe
                    "total_return": 0,
                    "max_drawdown": 0,
                    "market_regime": risk_result.get("market_regime", "unknown"),
                    "n_symbols": len(fetch_symbols),
                },
            )

            return {
                "status": "success",
                "cycle_id": cycle_id,
                "market_status": market_status,
                "universe_size": len(symbols),
                "screened_to": len(fetch_symbols),
                "signals": symbol_scores,
                "risk_level": risk_level,
                "target_weights": target_weights,
                "decisions": decisions,
                "executions": execution_results,
            }

        except Exception as e:
            logger.error("Cycle #%d error: %s", cycle_id, e)
            import traceback
            traceback.print_exc()
            if journal:
                journal.finish_cycle()
            return {"status": "error", "message": str(e), "cycle_id": cycle_id}

    def run_live_trading_loop(
        self,
        symbols: List[str],
        total_capital: float = 100000.0,
        interval_seconds: int = 300,
        max_positions: int = 10,
    ) -> None:
        """
        Continuously run live trading cycles with status panel and graceful shutdown.
        """
        journal = TradeJournal()
        cycle = 0

        symbol_display = ", ".join(symbols) if len(symbols) <= 15 else \
            f"{', '.join(symbols[:10])} ... (+{len(symbols) - 10} more)"

        currency_sym = self.market_config.currency_symbol if self.market_config else "$"

        print("\n" + "=" * 60)
        print("  LIANGHUA Auto Trading System - LIVE PAPER")
        print("=" * 60)
        print(f"  Market:      {self.market_config.market_name if self.market_config else 'US'}")
        print(f"  Universe:    {len(symbols)} stocks")
        print(f"                {symbol_display}")
        print(f"  Interval:    {interval_seconds}s")
        print(f"  Capital:     {currency_sym}{total_capital:,.0f}")
        print(f"  MaxPositions: {max_positions}")
        print("=" * 60)
        print("  Press Ctrl+C to stop.\n")

        try:
            while True:
                cycle += 1
                # ── Market status ──
                if self.calendar is not None:
                    ms = self.calendar.status_str()
                else:
                    ms = _legacy_market_status_str()

                # ── Status panel ──
                print(f"\n{'='*50}")
                print(f"  Cycle #{cycle}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Market: {ms}")

                # ── Account info from broker or legacy ──
                if self.broker is not None:
                    try:
                        acct = self.broker.get_account()
                        pv = acct.portfolio_value if hasattr(acct, 'portfolio_value') else float(getattr(acct, 'portfolio_value', 0))
                        cash = acct.cash if hasattr(acct, 'cash') else float(getattr(acct, 'cash', 0))
                        print(f"  Portfolio: {currency_sym}{pv:,.0f}  |  Cash: {currency_sym}{cash:,.0f}")
                        positions = self.broker.get_positions()
                        if positions:
                            print(f"  Positions: {len(positions)}")
                            for p in positions[:10]:
                                sym = p.symbol if hasattr(p, 'symbol') else p.get('symbol', '?')
                                qty = p.qty if hasattr(p, 'qty') else p.get('qty', 0)
                                mv = p.market_value if hasattr(p, 'market_value') else p.get('market_value', 0)
                                print(f"    {sym:<6} {float(qty):>8.1f} sh  {currency_sym}{float(mv):>10,.0f}")
                    except Exception as e:
                        logger.warning("Account display error: %s", e)
                elif _legacy_alpaca_service:
                    try:
                        acct = _legacy_alpaca_service.get_account()
                        pv = float(acct.portfolio_value) if hasattr(acct, 'portfolio_value') else 0
                        cash = float(acct.cash) if hasattr(acct, 'cash') else 0
                        print(f"  Portfolio: ${pv:,.0f}  |  Cash: ${cash:,.0f}")
                        positions = _legacy_alpaca_service.get_positions()
                        if positions:
                            print(f"  Positions: {len(positions)}")
                            for p in positions[:10]:
                                sym = getattr(p, 'symbol', '?')
                                qty = getattr(p, 'qty', 0)
                                mv = getattr(p, 'market_value', 0)
                                print(f"    {sym:<6} {float(qty):>8.1f} sh  ${float(mv):>10,.0f}")
                    except Exception:
                        pass
                print(f"{'='*50}")

                # Run cycle
                result = self.run_live_trading_cycle(
                    symbols=symbols,
                    total_capital=total_capital,
                    max_positions=max_positions,
                    journal=journal,
                )

                status = result.get("status", "?")
                if status == "success":
                    tw = result.get("target_weights", {})
                    n_orders = len(result.get("executions", []))
                    print(f"  >> Risk={result.get('risk_level','?')}  Targets={len(tw)}  Orders={n_orders}")
                    if tw:
                        print(f"  >> Weights: {', '.join(f'{s}:{w:.1%}' for s,w in list(tw.items())[:5])}")
                elif status == "skipped":
                    print(f"  >> Skipped: {result.get('reason', '')}")
                else:
                    print(f"  >> Error: {result.get('message', '')}")

                print(f"  -- Waiting {interval_seconds}s until next cycle...")
                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n\n  Shutting down gracefully...")
            print("  Trade journals saved to trade_journals/")
            print("  Goodbye.\n")

    def optimize_agent_prompts(self, agent_name: str, performance_metric: str, current_value: float, target_value: float) -> str:
        """
        Optimize agent instructions using a Meta-Agent approach.
        """
        logger.info(f"Optimizing prompts for {agent_name}. Current {performance_metric}: {current_value:.2f}, Target: {target_value}")
        
        # Identify the agent
        target_agent = None
        if agent_name == "Alpha":
            target_agent = self.alpha_agent.agent
        elif agent_name == "Risk":
            target_agent = self.risk_agent.agent
        elif agent_name == "Portfolio":
            target_agent = self.portfolio_agent.agent
            
        if not target_agent:
            logger.error(f"Agent {agent_name} not found")
            return "Optimization failed: Agent not found"
            
        # Construct the optimization prompt
        meta_prompt = f"""
        You are a Meta-Agent optimizing trading agents.
        The {agent_name} Agent is underperforming.
        Metric: {performance_metric}
        Current Value: {current_value}
        Target Value: {target_value}
        
        Current Instructions:
        {target_agent.instructions}
        
        Please rewrite the instructions to improve performance. Focus on:
        1. More robust signal generation
        2. Better risk management
        3. Adapting to market conditions
        
        Return ONLY the new instructions.
        """
        
        # Call LLM if available
        new_instructions = target_agent.instructions # Default to current
        
        if hasattr(target_agent, 'client') and target_agent.client:
            try:
                response = target_agent.client.chat.completions.create(
                    model="gpt-4o", # Use strong model for optimization
                    messages=[{"role": "user", "content": meta_prompt}]
                )
                new_instructions = response.choices[0].message.content
                logger.info("Prompts optimized using LLM")
            except Exception as e:
                logger.warning(f"LLM optimization failed: {e}. Appending refinement rule.")
                new_instructions += f"\n\nRefinement ({datetime.now().date()}): Be more conservative in signal generation when volatility is high."
        else:
            logger.info("LLM not available. Appending refinement rule.")
            new_instructions += f"\n\nRefinement ({datetime.now().date()}): Focus on trend-following and reduce position size during drawdowns."
            
        # Update the agent's instructions
        target_agent.instructions = new_instructions
        return new_instructions

    def run_agentic_pipeline(self, user_request: str):
        """Run the pipeline using the Manager Agent"""
        logger.info(f"Manager Agent processing: {user_request}")
        return self.manager_agent.run(user_request, max_turns=10)

if __name__ == "__main__":
    print("=" * 60)
    print("  Lianghua Orchestrator Demo")
    print("  Memory + RAG + Multi-Agent Pipeline")
    print("=" * 60)

    orchestrator = Orchestrator()

    # Demo 1: RAG knowledge search
    print("\n--- Demo 1: RAG Knowledge Search ---")
    try:
        from agent_pools.memory.agent_rag_client import get_rag_client
        rag = get_rag_client()
        results = rag.query("momentum factor construction from price volume", n_results=2)
        for i, r in enumerate(results, 1):
            print(f"  Result {i}: {r[:150]}...")
    except Exception as e:
        print(f"  RAG skipped: {e}")

    # Demo 2: Memory store/query
    print("\n--- Demo 2: Memory System ---")
    try:
        from agent_pools.memory.agent_memory_client import AgentMemoryClient
        client = AgentMemoryClient()
        client.store_reflection(
            agent_name="Orchestrator",
            strategy_name="pipeline_v1",
            issue="overfitting on small universe",
            lesson_learned="Use at least 100 stocks and walk-forward validation",
        )
        print("  Stored reflection: pipeline_v1 overfitting lesson")
        lessons = client.retrieve_lessons_by_issue("overfitting")
        print(f"  Retrieved {len(lessons)} lessons")
        client.close()
    except Exception as e:
        print(f"  Memory skipped (Neo4j not running): {e}")

    # Demo 3: Agentic pipeline
    print("\n--- Demo 3: Agentic Pipeline ---")
    request = "Search knowledge base for 'momentum factor', then fetch data for AAPL (2023-01-01 to 2023-06-01) and ask Alpha Agent to analyze it."
    result = orchestrator.run_agentic_pipeline(request)
    print(f"\nPipeline result: {str(result)[:500]}...")
    print("\nDemo complete.")
