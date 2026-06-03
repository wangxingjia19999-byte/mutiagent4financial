# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lianghua (量化) is a multi-agent collaborative quantitative investment research system. It uses LLM-driven agents orchestrated together to cover the full pipeline: market universe screening → alpha signal generation → risk control → portfolio optimization → backtesting → paper trading execution.

The system integrates Neo4j for graph-based memory (storing strategy lessons) and ChromaDB for RAG (retrieving Alpha101 paper knowledge).

## Architecture

The system follows an **Orchestrator + Agent-as-Tool** pattern:

- **Orchestrator** (`orchestrator_demo/orchestrator.py`) — Central coordinator that chains agents together. It manages data fetching, agent invocation order, and result aggregation.
- **Alpha Agent** (`agent_pools/alpha_agent_demo/alpha_signal_agent.py`) — Generates trading signals using technical indicators (RSI, MACD, Bollinger) and ML models (linear, random forest).
- **Risk Agent** (`agent_pools/risk_agent_demo/risk_signal_agent.py`) — Assesses market risk via volatility and VaR calculations.
- **Portfolio Agent** (`agent_pools/portfolio_agent_demo/portfolio_agent.py`) — Constructs target portfolio weights from alpha signals adjusted for risk level.
- **Backtest Agent** (`agent_pools/backtest_agent_pool/backtest_agent.py`) — Runs backtests using Qlib framework or simplified simulation.
- **Execution Agent** (`agent_pools/execution_agent_demo/execution_agent_demo/execution_agent.py`) — Executes trades via Alpaca Trading API with risk validation.

Each agent uses a custom `Agent` class (`agent_pools/alpha_agent_pool/local_agents.py`) that wraps OpenAI API calls with function-calling support. Agents expose their capabilities as tools that other agents can invoke.

## Key Patterns

- **Agent-as-Tool**: Agents can be called as tools by the orchestrator or other agents via `agent.as_tool()`.
- **Context passing**: Agents communicate through a shared `context` dict rather than direct return values.
- **Graceful degradation**: Neo4j, Qlib, and Alpaca all have mock/fallback modes when unavailable.
- **Train/Test split**: The orchestrator always fetches extended historical data (365 days lookback) and splits into train/test to avoid leakage.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run backtest (S&P 500 level, with RAG + memory)
python run_paper_trading.py --mode backtest --universe sp500 --start 2024-01-01 --end 2024-03-01

# Run single live trading cycle
python run_paper_trading.py --mode once --universe nasdaq100

# Run continuous auto-trading
python run_paper_trading.py --mode continuous --universe liquid --interval 300

# Disable RAG / memory (faster startup)
python run_paper_trading.py --mode backtest --universe sp500 --no-rag --no-memory

# Rolling weekly backtest (walk-forward validation)
python run_paper_trading.py --mode backtest --symbol AAPL,MSFT --start 2024-01-01 --end 2024-03-01 --rolling

# Run sub-module demos
python agent_pools/alpha_agent_pool/alpha_research_agent.py  # Alpha research demo
python agent_pools/risk_agent_demo/example_usage.py           # Risk agent demo
python orchestrator_demo/orchestrator.py                       # Orchestrator demo
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:
- `POE_API_KEY` — Required. Poe API key (mapped to OPENAI_API_KEY internally)
- `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` — Required for trading and market data
- `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` — Optional. For graph memory
- `TUSHARE_TOKEN` — Optional. For A-share data

The `poe_config.py` module transparently maps `POE_*` env vars to `OPENAI_*` vars so all OpenAI-compatible clients work with Poe.

## Memory System

Two memory backends, both optional:

1. **Neo4j Graph Memory** (`agent_pools/memory/agent_memory_client.py`) — Stores structured reflections (strategy lessons, failures). Use `AgentMemoryClient` to store/query.
2. **ChromaDB RAG** (`agent_pools/memory/agent_rag_client.py`) — Vector search over Alpha101 paper. Auto-builds index from `knowledge/1601.00991v3.pdf` on first use.

Both degrade gracefully — if Neo4j/ChromaDB aren't running, the pipeline continues without them.

## Data Flow

```
run_paper_trading.py
  → Orchestrator.__init__()  (creates all agents)
  → resolve_symbols()        (via market_universe.py or --symbol)
  → _init_rag() / _init_memory()  (optional)
  → orch.run_pipeline()      (backtest) or orch.run_live_trading_cycle() (live)
    → fetch_data()           (Alpaca → yfinance → mock fallback)
    → alpha_agent.generate_signals_from_data()
    → risk_agent.generate_risk_signals_from_data()
    → portfolio_agent.inference()
    → backtest_agent.run_simple_backtest_paper_interface() or execution_agent.execute_orders_direct()
  → _store_pipeline_reflections()  (save lessons to Neo4j)
```

## Important Files

- `run_paper_trading.py` — Main entry point. Handles CLI args, RAG/memory init, and result display.
- `orchestrator_demo/orchestrator.py` — Orchestrator with data fetching, pipeline methods, and live trading loop.
- `agent_pools/alpha_agent_pool/local_agents.py` — Custom Agent framework with OpenAI function calling.
- `agent_pools/market_universe.py` — Fetches tradeable US stocks from Alpaca with price/volume filtering.
- `agent_pools/poe_config.py` — Maps Poe env vars to OpenAI-compatible vars.
- `agent_pools/memory/agent_memory_client.py` — Synchronous Neo4j memory client.
- `agent_pools/memory/agent_rag_client.py` — ChromaDB RAG client with auto-indexing.
