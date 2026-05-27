"""
Portfolio Agent using OpenAI Agent SDK

This agent implements the Portfolio Construction model.
Supports ReAct workflow.
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent_pools.poe_config import setup_poe_env, resolve_poe_model

setup_poe_env()

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
alpha_agent_pool_path = parent_dir / "alpha_agent_pool"
sys.path.append(str(alpha_agent_pool_path))

# Import Local Agents SDK
import nest_asyncio
nest_asyncio.apply()
from agent_pools.alpha_agent_pool.local_agents import Agent, function_tool


# ==============================
# Internal Logic
# ==============================

def _construct_portfolio_impl(
    alpha_signals: Any,
    risk_signals: Any,
    transaction_costs: Any,
    current_portfolio: Any = None,
    total_capital: float = 100000.0,
    max_positions: int = 20,
) -> Dict[str, Any]:
    """Build target portfolio weights from alpha signals, adjusted for risk level."""
    try:
        # 1. Parse alpha signals
        if isinstance(alpha_signals, dict):
            raw_signals = alpha_signals
        elif isinstance(alpha_signals, (pd.Series,)):
            raw_signals = alpha_signals.to_dict()
        else:
            raw_signals = {}

        # 2. Determine risk level and capital allocation
        risk_level = "LOW"
        if isinstance(risk_signals, dict):
            risk_level = risk_signals.get("overall_risk_level", "LOW")

        capital_allocation = {"LOW": 1.0, "MODERATE": 0.80, "HIGH": 0.50}
        alloc_pct = capital_allocation.get(risk_level, 0.80)
        investable_capital = total_capital * alloc_pct

        # 3. Separate positive (long) and negative (exit) signals
        positive = {s: v for s, v in raw_signals.items() if v > 0}
        negative = {s: v for s, v in raw_signals.items() if v <= 0}

        # 4. Equal-risk-weighted allocation for positive signals
        target_weights: Dict[str, float] = {}
        exit_candidates: List[str] = list(negative.keys())

        if positive:
            # Rank by score, take top max_positions
            ranked = sorted(positive.items(), key=lambda x: x[1], reverse=True)
            selected = ranked[:max_positions]

            if selected:
                # Equal weight among selected (diversified), scaled by risk allocation
                weight_per_position = alloc_pct / len(selected)
                for symbol, score in selected:
                    target_weights[symbol] = weight_per_position

        return {
            "status": "success",
            "target_weights": target_weights,
            "risk_adjustment": {
                "risk_level": risk_level,
                "capital_allocation": alloc_pct,
                "investable_capital": investable_capital,
            },
            "exit_candidates": exit_candidates,
            "selected_assets": list(target_weights.keys()),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def generate_orders(
    target_weights: Dict[str, float],
    current_positions: Dict[str, float],
    total_capital: float,
    market_prices: Dict[str, float],
    min_trade_value: float = 100.0,
) -> List[Dict[str, Any]]:
    """
    Compute the orders needed to move from current_positions to target_weights.

    Args:
        target_weights: {symbol: weight} — desired portfolio weights
        current_positions: {symbol: market_value} — current holdings (market value)
        total_capital: total portfolio value
        market_prices: {symbol: price} — current market prices
        min_trade_value: minimum $ value to bother trading

    Returns:
        List of order dicts: {symbol, side, qty, order_type, limit_price, reason}
    """
    orders: List[Dict[str, Any]] = []

    all_symbols = set(list(target_weights.keys()) + list(current_positions.keys()))

    for symbol in all_symbols:
        target_weight = target_weights.get(symbol, 0.0)
        current_value = current_positions.get(symbol, 0.0)
        target_value = target_weight * total_capital
        diff = target_value - current_value

        if abs(diff) < min_trade_value:
            continue

        price = market_prices.get(symbol, 0)
        if price <= 0:
            continue

        qty = int(abs(diff) / price)
        if qty <= 0:
            continue

        if diff > 0:
            orders.append({
                "symbol": symbol,
                "side": "buy",
                "qty": qty,
                "order_type": "market",
                "limit_price": round(price * 1.005, 2),  # 0.5% above market for limit
                "estimated_value": qty * price,
                "reason": f"target_weight={target_weight:.3f}, current_value=${current_value:,.0f}, diff=+${diff:,.0f}",
            })
        else:
            orders.append({
                "symbol": symbol,
                "side": "sell",
                "qty": qty,
                "order_type": "market",
                "limit_price": round(price * 0.995, 2),  # 0.5% below market for limit
                "estimated_value": qty * price,
                "reason": f"target_weight={target_weight:.3f}, current_value=${current_value:,.0f}, diff=${diff:,.0f}",
            })

    # Sells first (raise cash), then buys
    sells = [o for o in orders if o["side"] == "sell"]
    buys = [o for o in orders if o["side"] == "buy"]
    return sells + buys


# ==============================
# Tools
# ==============================

@function_tool
def run_portfolio_pipeline(ctx: dict) -> str:
    """Execute standard portfolio construction pipeline."""
    print("DEBUG: [Portfolio] run_portfolio_pipeline (Macro) INVOKED")
    try:
        alpha_signals = ctx.get('alpha_signals')
        risk_signals = ctx.get('risk_signals')
        transaction_costs = ctx.get('transaction_costs')
        current_portfolio = ctx.get('current_portfolio')
        total_capital = ctx.get('total_capital', 100000.0)
        max_positions = ctx.get('max_positions', 10)

        result = _construct_portfolio_impl(
            alpha_signals, risk_signals, transaction_costs,
            current_portfolio, total_capital, max_positions
        )
        ctx['result'] = result
        return f"Portfolio constructed. Assets: {len(result.get('target_weights', {}))}"
    except Exception as e:
        return f"Error: {e}"


@function_tool
def construct_portfolio_tool(ctx: dict, max_allocation: float = 1.0) -> str:
    """
    Construct portfolio weights from signals in context.
    """
    print(f"DEBUG: [Portfolio] construct_portfolio_tool INVOKED")
    try:
        alpha_signals = ctx.get('alpha_signals')
        if not alpha_signals:
            return "Error: No alpha signals."

        # Simple Equal Weight Logic for custom path
        sorted_assets = sorted(alpha_signals.items(), key=lambda x: x[1], reverse=True)
        top_k = ctx.get('max_positions', 20)
        selected = sorted_assets[:top_k]
        weights = {}
        if selected:
            w = max_allocation / len(selected)
            for asset, score in selected:
                if score > 0:
                    weights[asset] = w

        ctx['target_weights'] = weights
        return f"Constructed weights for {len(weights)} assets."
    except Exception as e:
        return f"Error: {e}"


@function_tool
def submit_portfolio_tool(ctx: dict) -> str:
    """Submit final portfolio."""
    print("DEBUG: [Portfolio] submit_portfolio_tool INVOKED")
    try:
        weights = ctx.get('target_weights')
        if weights is None:
            return "Error: No weights found."

        result = {
            "status": "success",
            "target_weights": weights,
            "message": "Custom portfolio submitted",
        }
        ctx['result'] = result
        return "Portfolio submitted."
    except Exception as e:
        return f"Error: {e}"


# ==============================
# Portfolio Agent
# ==============================

class PortfolioAgent:
    def __init__(
        self,
        name: str = "PortfolioAgent",
        model: str = None,
        mode: str = "backtest",
    ):
        self.name = name
        self.model = model or resolve_poe_model("openai/gpt-4o-mini")
        self.mode = mode

        self.tools = [
            run_portfolio_pipeline,
            construct_portfolio_tool,
            submit_portfolio_tool,
        ]

        self.agent = Agent(
            name=name,
            instructions=f"""
            You are a Portfolio Agent.
            Choose a path:
            1. FAST PATH: Use 'run_portfolio_pipeline'.
            2. CUSTOM PATH: Use 'construct_portfolio_tool' then 'submit_portfolio_tool'.
            Current Mode: {self.mode.upper()}
            """,
            model=self.model,
            tools=self.tools,
        )

    def run(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.agent.run(user_request, context=context, max_turns=10)

    def inference(
        self,
        alpha_signals: Dict[str, float],
        risk_signals: Dict[str, Any],
        transaction_costs: Optional[Dict[str, float]] = None,
        current_portfolio: Optional[Dict[str, float]] = None,
        total_capital: float = 100000.0,
        max_positions: int = 20,
    ) -> Dict[str, Any]:
        tx_costs = transaction_costs or {"fixed_cost": 1.0, "slippage": 0.0001}

        context = {
            'alpha_signals': alpha_signals,
            'risk_signals': risk_signals,
            'transaction_costs': tx_costs,
            'current_portfolio': current_portfolio,
            'total_capital': total_capital,
            'max_positions': max_positions,
        }

        # Use local implementation directly — faster and more reliable than LLM round-trip
        result = _construct_portfolio_impl(
            alpha_signals, risk_signals, tx_costs,
            current_portfolio, total_capital, max_positions
        )
        return result


if __name__ == "__main__":
    print("Portfolio Agent Initialized")
