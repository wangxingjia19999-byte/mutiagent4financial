
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
        is_market_open, market_status_str, alpaca_service,
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

# ------------------------------------------------------------------------------
# Data Client
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
    def __init__(self):
        self.api_key = os.getenv("ALPACA_API_KEY")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.poe_model = resolve_poe_model("GPT-5.4")
        
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not found. Agents might fail.")
            
        # Initialize Sub-Agents
        self.alpha_agent = AlphaSignalAgent(name="AlphaCore", model=self.poe_model)
        self.risk_agent = RiskSignalAgent(name="RiskCore", model=self.poe_model)
        self.portfolio_agent = PortfolioAgent(name="PortfolioCore", model=self.poe_model)
        
        self.execution_agent = ExecutionAgent(
            alpaca_api_key=self.api_key, 
            alpaca_secret_key=self.secret_key, 
            paper=True
        )
        self.backtest_agent = BacktestAgent()
        
        # Data Client
        if StockHistoricalDataClient and self.api_key:
            self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        else:
            self.data_client = None
            
        # Pipeline Context (Shared Memory)
        self.pipeline_context = {}
        
        # Initialize Manager with Agent-as-Tool pattern
        self._initialize_manager_agent()

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

        # 3. Create Manager Agent with Agents as Tools
        # This matches the "Agent as Tool" pattern from the docs
        
        self.manager_agent = Agent(
            name="OrchestratorAgent",
            instructions=(
                "You are a trading strategy manager. You use the tools given to you to execute the pipeline. "
                "1. Fetch data first. "
                "2. Ask Alpha Agent to analyze. "
                "3. Ask Risk Agent to assess. "
                "4. Ask Portfolio Agent to construct portfolio. "
                "5. Ask Execution Agent to trade OR Backtest Agent to simulate."
            ),
            tools=[
                # Helper Tool
                fetch_market_data,
                
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
        """Fetch historical data from Alpaca or Mock"""
        if isinstance(symbols, str):
            symbols = [symbols]
            
        logger.info(f"Fetching data for {symbols} from {start_date} to {end_date}")
        
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
                    if isinstance(df.columns, pd.MultiIndex):
                        if df.columns.nlevels > 1:
                            df.columns = df.columns.droplevel(1)
                            
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
        Fetch real-time prices from Alpaca for order sizing.
        Uses batched snapshot requests for efficiency with large symbol lists.
        """
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
        
        logger.info(f"Running pipeline for {symbol_str} from {start_date} to {end_date}")
        
        # 1. Data Fetching
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            # ROLLING WINDOW: Fetch 1 year prior for training to avoid leakage
            lookback_days = 365
            fetch_start_dt = start_dt - timedelta(days=lookback_days)
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

            # 2. Alpha Generation
            # Define some default factors/indicators for the demo
            factors = [
                {"factor_name": "momentum_20", "factor_type": "technical", "calculation_method": "expression", "expression": "close / Ref(close, 20) - 1", "lookback_period": 20}
            ]
            indicators = ["RSI", "MACD", "Bollinger"]
            
            alpha_result = self.alpha_agent.generate_signals_from_data(
                data=test_data, # Predict on Test
                factors=factors, 
                indicators=indicators, 
                model_type="linear", 
                signal_threshold=0.0,
                train_data=train_data # Train on History
            )
            
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
            )

            if portfolio_result.get("status") != "success":
                logger.warning(f"Portfolio construction failed: {portfolio_result.get('message')}")

            # 5. Backtest — use the original MultiIndex signals for the backtest engine
            signals_series = pd.Series(predictions_dict)

            if not isinstance(signals_series.index, pd.MultiIndex):
                if len(symbols) == 1:
                    signals_series.index = pd.MultiIndex.from_product(
                        [signals_series.index, [symbols[0]]], names=['datetime', 'instrument'])
                else:
                    signals_series.index.names = ['datetime', 'instrument']
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
            backtest_result["exit_candidates"] = portfolio_result.get("exit_candidates", [])

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
            
            # 1. Fetch All Data (The "World" has data, but Agent sees it incrementally)
            fetch_start = start_dt - timedelta(days=lookback_days)
            full_data = self.fetch_data(symbols, fetch_start, end_dt)
            
            if full_data.empty or 'date' not in full_data.columns:
                return {"status": "error", "message": "Data fetch failed"}
                
            full_data['date'] = pd.to_datetime(full_data['date']).dt.tz_localize(None)
            
            # 2. Weekly Loop
            current_dt = start_dt
            all_signals_list = []
            
            while current_dt < end_dt:
                next_week_dt = current_dt + timedelta(weeks=1)
                if next_week_dt > end_dt: next_week_dt = end_dt
                
                # Define Data Slices
                # Train: [current_dt - lookback, current_dt)
                # Test: [current_dt, next_week_dt)
                
                train_start = current_dt - timedelta(days=lookback_days)
                train_data = full_data[
                    (full_data['date'] >= train_start) & 
                    (full_data['date'] < current_dt)
                ].copy()
                
                test_data = full_data[
                    (full_data['date'] >= current_dt) & 
                    (full_data['date'] < next_week_dt)
                ].copy()
                
                if test_data.empty:
                    current_dt = next_week_dt
                    continue
                    
                logger.info(f"📅 Rolling Step: {current_dt.date()} -> {next_week_dt.date()} (Train: {len(train_data)}, Test: {len(test_data)})")
                
                # Generate Signals
                factors = [
                    {"factor_name": "momentum_20", "factor_type": "technical", "calculation_method": "expression", "expression": "close / Ref(close, 4) - 1", "lookback_period": 4}
                ]
                indicators = ["RSI", "MACD", "Bollinger"]
                
                alpha_result = self.alpha_agent.generate_signals_from_data(
                    data=test_data, 
                    train_data=train_data,
                    factors=factors,
                    indicators=indicators,
                    model_type="linear",
                    signal_threshold=0.0
                )
                
                if alpha_result['status'] == 'success':
                    sigs = alpha_result.get('signals', {})
                    if sigs:
                        sig_series = pd.Series(sigs)
                        all_signals_list.append(sig_series)
                
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
                     full_signals_series.index.names = ['datetime', 'instrument']
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

        market_status = market_status_str()
        if journal:
            journal.start_cycle(cycle_id, market_status)

        if not is_market_open():
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

            # 1. Fetch latest market data for candidates + currently held positions
            if alpaca_service:
                held_symbols = []
                try:
                    for p in alpaca_service.get_positions():
                        s = getattr(p, "symbol", "")
                        if s and s not in candidates:
                            held_symbols.append(s)
                except Exception:
                    pass
                fetch_symbols = list(dict.fromkeys(candidates + held_symbols))  # dedupe, preserve order
            else:
                fetch_symbols = candidates

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

            # 2. Alpha signals
            factors = [
                {"factor_name": "momentum_20", "factor_type": "technical",
                 "calculation_method": "expression", "expression": "close / Ref(close, 20) - 1",
                 "lookback_period": 20},
            ]
            indicators = ["RSI", "MACD", "Bollinger"]

            alpha_result = self.alpha_agent.generate_signals_from_data(
                data=test_data, train_data=train_data,
                factors=factors, indicators=indicators,
                model_type="linear", signal_threshold=0.0,
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
            )

            target_weights = portfolio_result.get("target_weights", {})
            risk_level = risk_result.get("overall_risk_level", "UNKNOWN")

            if journal:
                journal.log_signals(symbol_scores, risk_level)

            # 6. Get current positions from Alpaca
            current_positions: Dict[str, float] = {}
            if alpaca_service:
                try:
                    for p in alpaca_service.get_positions():
                        sym = getattr(p, "symbol", "")
                        if sym:
                            current_positions[sym] = float(getattr(p, "market_value", 0))
                    logger.info("Current positions: %d held", len(current_positions))
                except Exception as e:
                    logger.warning("Failed to get Alpaca positions: %s", e)

            # 7. Real-time prices (only for symbols in target_weights + current positions)
            all_active = list(set(list(target_weights.keys()) + list(current_positions.keys())))
            market_prices = self.fetch_realtime_prices(all_active) if all_active else {}

            # 8. Generate orders from weight diffs
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

            # 9. Execute orders
            execution_results: List[Dict[str, Any]] = []
            if orders:
                execution_results = self.execution_agent.execute_orders_direct(orders)
                logger.info("Executed %d orders: %s", len(execution_results),
                            [(r.get("symbol"), r.get("status")) for r in execution_results])

                if journal:
                    for i, order in enumerate(orders):
                        result = execution_results[i] if i < len(execution_results) else {"status": "unknown"}
                        journal.log_execution(order, result)

            if journal:
                journal.finish_cycle()

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

        print("\n" + "=" * 60)
        print("  LIANGHUA Auto Trading System - LIVE PAPER")
        print("=" * 60)
        print(f"  Universe:    {len(symbols)} stocks")
        print(f"                {symbol_display}")
        print(f"  Interval:    {interval_seconds}s")
        print(f"  Capital:     ${total_capital:,.0f}")
        print(f"  MaxPositions: {max_positions}")
        print("=" * 60)
        print("  Press Ctrl+C to stop.\n")

        try:
            while True:
                cycle += 1
                ms = market_status_str()

                # Status panel
                print(f"\n{'='*50}")
                print(f"  Cycle #{cycle}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Market: {ms}")
                if alpaca_service:
                    try:
                        acct = alpaca_service.get_account()
                        pv = float(acct.portfolio_value) if hasattr(acct, 'portfolio_value') else 0
                        cash = float(acct.cash) if hasattr(acct, 'cash') else 0
                        print(f"  Portfolio: ${pv:,.0f}  |  Cash: ${cash:,.0f}")
                        positions = alpaca_service.get_positions()
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
    orchestrator = Orchestrator()
    
    print("\n--- Agentic Pipeline Demo (Agent-as-Tool Pattern) ---")
    # Simulate a user request that triggers the agents
    request = "Fetch data for AAPL, MSFT (2023-01-01 to 2023-06-01) and then ask Alpha Agent to analyze it."
    
    result = orchestrator.run_agentic_pipeline(request)
    print("\nFinal Result:")
    print(result)
