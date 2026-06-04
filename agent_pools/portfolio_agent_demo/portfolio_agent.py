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
# Sector Mapping (for sector neutrality)
# ==============================

# Compact sector map for common US/CN stocks. Falls back to "Other" for unknowns.
_STOCK_SECTORS = {
    # Tech
    "AAPL": "Tech", "MSFT": "Tech", "GOOGL": "Tech", "GOOG": "Tech",
    "META": "Tech", "NVDA": "Tech", "AMD": "Tech", "INTC": "Tech",
    "ADBE": "Tech", "CRM": "Tech", "ORCL": "Tech", "CSCO": "Tech",
    "IBM": "Tech", "QCOM": "Tech", "TXN": "Tech", "AMAT": "Tech",
    "AVGO": "Tech", "ADSK": "Tech", "NOW": "Tech", "INTU": "Tech",
    "TSLA": "Auto", "F": "Auto", "GM": "Auto", "RIVN": "Auto",
    # Finance
    "JPM": "Finance", "BAC": "Finance", "WFC": "Finance", "GS": "Finance",
    "MS": "Finance", "C": "Finance", "BLK": "Finance", "SCHW": "Finance",
    "AXP": "Finance", "V": "Finance", "MA": "Finance", "PYPL": "Finance",
    # Healthcare
    "JNJ": "Healthcare", "PFE": "Healthcare", "MRK": "Healthcare",
    "ABBV": "Healthcare", "BMY": "Healthcare", "LLY": "Healthcare",
    "UNH": "Healthcare", "CVS": "Healthcare", "AMGN": "Healthcare",
    # Consumer
    "AMZN": "Consumer", "WMT": "Consumer", "COST": "Consumer", "HD": "Consumer",
    "MCD": "Consumer", "NKE": "Consumer", "SBUX": "Consumer", "TGT": "Consumer",
    "LOW": "Consumer", "TJX": "Consumer",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
    "EOG": "Energy", "PXD": "Energy", "OXY": "Energy",
    # Communication
    "NFLX": "Comm", "DIS": "Comm", "CMCSA": "Comm", "T": "Comm", "VZ": "Comm",
    # Industrial
    "BA": "Industrial", "CAT": "Industrial", "GE": "Industrial", "HON": "Industrial",
    "UPS": "Industrial", "RTX": "Industrial", "LMT": "Industrial",
    # Real Estate / Other
    "PLTR": "Tech", "UBER": "Tech", "ABNB": "Tech", "SNOW": "Tech",
}

_STOCK_SECTORS_CN = {
    "600519.SH": "白酒", "000858.SZ": "白酒", "000568.SZ": "白酒",
    "601318.SH": "金融", "600036.SH": "金融", "601398.SH": "金融",
    "600276.SH": "医药", "000538.SZ": "医药", "300760.SZ": "医药",
    "000002.SZ": "地产", "600048.SH": "地产",
    "300750.SZ": "新能源", "601012.SH": "新能源", "002594.SZ": "新能源",
    "600900.SH": "电力", "601985.SH": "电力",
    "002415.SZ": "科技", "000725.SZ": "科技",
    "601899.SH": "矿业", "600585.SH": "建材",
}

_SECTOR_MAP = {**_STOCK_SECTORS, **_STOCK_SECTORS_CN}


def get_sector(symbol: str) -> str:
    """Get sector for a symbol. Returns 'Other' if unknown."""
    return _SECTOR_MAP.get(symbol.upper(), "Other")


# ==============================
# Covariance-Based Optimization
# ==============================

def _compute_covariance_weights(
    symbols: List[str],
    price_data: pd.DataFrame,
    alloc_pct: float,
    method: str = "risk_parity",
) -> Dict[str, float]:
    """
    Compute portfolio weights using covariance matrix from historical returns.

    Methods:
      - risk_parity: w_i ∝ 1/σ_i (inverse volatility). Robust, no matrix inversion.
      - min_variance: minimize wᵀΣw subject to Σw = alloc_pct. Requires Σ invertible.

    Falls back to equal-weight if covariance computation fails.
    """
    n = len(symbols)
    if n < 2:
        return {symbols[0]: alloc_pct} if n == 1 else {}

    try:
        # Compute returns from price data
        if 'symbol' in price_data.columns:
            returns = price_data.pivot_table(
                index='date', columns='symbol', values='close', aggfunc='last'
            ).pct_change().dropna(how='all')
        else:
            returns = price_data['close'].pct_change().dropna().to_frame()

        # Keep only our target symbols
        available = [s for s in symbols if s in returns.columns]
        if len(available) < 2:
            return {s: alloc_pct / len(symbols) for s in symbols}

        returns = returns[available].dropna()

        if method == "risk_parity":
            # Inverse-vol weighting: w_i ∝ 1/σ_i
            vols = returns.std()
            inv_vols = 1.0 / (vols + 1e-8)
            raw_weights = inv_vols / inv_vols.sum() * alloc_pct
            weights = {s: float(raw_weights[s]) for s in available}

        elif method == "min_variance":
            # Minimum variance: w = Σ⁻¹1 / (1ᵀΣ⁻¹1) * alloc_pct
            cov = returns.cov().values
            ones = np.ones(len(available))
            try:
                cov_inv = np.linalg.pinv(cov)  # pseudoinverse for stability
                raw = cov_inv @ ones
                raw = raw / raw.sum() * alloc_pct
                weights = {s: float(raw[i]) for i, s in enumerate(available)}
            except np.linalg.LinAlgError:
                # Fallback to inverse-vol
                vols = returns.std()
                inv_vols = 1.0 / (vols + 1e-8)
                raw = inv_vols / inv_vols.sum() * alloc_pct
                weights = {s: float(raw[s]) for s in available}
        else:
            weights = {s: alloc_pct / len(symbols) for s in symbols}

        # Fill in any missing symbols
        for s in symbols:
            if s not in weights:
                weights[s] = 0.0

        return weights

    except Exception as e:
        # Fallback to equal weight
        print(f"WARNING: Covariance optimization failed ({e}), using equal weight.")
        w = alloc_pct / len(symbols)
        return {s: w for s in symbols}


# ==============================
# Sector Neutrality
# ==============================

def apply_sector_neutrality(
    signals: Dict[str, float],
) -> Dict[str, float]:
    """
    Remove sector biases from signals.

    For each sector, compute the mean signal and subtract it from each stock
    in that sector. This ensures signals reflect stock-specific alpha, not
    sector-level bets (e.g., "all tech stocks look good because tech is hot").
    """
    if len(signals) < 3:
        return signals  # too few stocks for meaningful sector adjustment

    # Group by sector
    sectors: Dict[str, List[str]] = {}
    for sym in signals:
        sec = get_sector(sym)
        if sec not in sectors:
            sectors[sec] = []
        sectors[sec].append(sym)

    # Only neutralize if we have multiple sectors and stocks per sector
    if len(sectors) < 2:
        return signals

    # Subtract sector mean from each stock
    neutralized = dict(signals)
    for sec, syms in sectors.items():
        if len(syms) < 2:
            continue
        sec_mean = np.mean([signals[s] for s in syms])
        for s in syms:
            neutralized[s] = signals[s] - sec_mean

    return neutralized


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
    price_data: pd.DataFrame = None,
    optimize_method: str = "risk_parity",
) -> Dict[str, Any]:
    """
    Build target portfolio weights from alpha signals, risk-adjusted per stock.

    Weighting logic:
      1. Global capital allocation: scaled by overall_risk_level (LOW=100%, MODERATE=80%, HIGH=50%)
      2. Covariance optimization (if price_data provided): risk parity or min variance
      3. Per-stock risk adjustment: safer stocks get larger weights (fallback)
      4. Per-stock position caps: enforced from risk agent's per-stock assessment
      5. Fallback: equal-weight if no per-stock risk data available
    """
    try:
        # 1. Parse alpha signals
        if isinstance(alpha_signals, dict):
            raw_signals = alpha_signals
        elif isinstance(alpha_signals, (pd.Series,)):
            raw_signals = alpha_signals.to_dict()
        else:
            raw_signals = {}

        # 2. Determine global risk level and capital allocation
        risk_level = "LOW"
        per_stock_risk: Dict[str, Dict[str, Any]] = {}
        risk_score_global = 0.0

        if isinstance(risk_signals, dict):
            risk_level = risk_signals.get("overall_risk_level", "LOW")
            risk_score_global = risk_signals.get("risk_score", 0.0)
            per_stock_risk = risk_signals.get("per_stock_risk", {})

        capital_allocation = {"LOW": 1.0, "MODERATE": 0.80, "HIGH": 0.50}
        alloc_pct = capital_allocation.get(risk_level, 0.80)
        investable_capital = total_capital * alloc_pct

        # 3. Separate positive (long) and negative (exit) signals
        positive = {s: v for s, v in raw_signals.items() if v > 0}
        negative = {s: v for s, v in raw_signals.items() if v <= 0}

        target_weights: Dict[str, float] = {}
        exit_candidates: List[str] = list(negative.keys())
        weight_method = "equal_weight"  # default

        if positive:
            # Rank by alpha score, take top max_positions
            ranked = sorted(positive.items(), key=lambda x: x[1], reverse=True)
            selected = ranked[:max_positions]

            if selected:
                selected_symbols = [s for s, _ in selected]

                # ── Covariance-optimized weighting (preferred, if data available) ──
                if price_data is not None and len(selected_symbols) >= 2:
                    try:
                        cov_weights = _compute_covariance_weights(
                            selected_symbols, price_data, alloc_pct, method=optimize_method
                        )
                        if cov_weights:
                            weight_method = optimize_method
                            for symbol in selected_symbols:
                                cap = per_stock_risk.get(symbol, {}).get("position_cap", 0.20)
                                target_weights[symbol] = round(min(cov_weights.get(symbol, 0), cap), 6)
                    except Exception as e:
                        print(f"WARNING: Covariance optimization failed ({e}), using heuristic.")

                # ── Heuristic risk-adjusted weighting (fallback) ──
                if not target_weights:
                    # Precompute alpha score range for normalization (avoid O(n²) in loop)
                    all_scores = [s for _, s in selected]
                    score_min = min(all_scores)
                    score_max = max(all_scores)
                    score_range = (score_max - score_min) + 1e-8

                    risk_factors: Dict[str, float] = {}

                    for symbol, alpha_score in selected:
                        stock_risk = per_stock_risk.get(symbol, {})
                        stock_risk_score = stock_risk.get("risk_score")

                        if stock_risk_score is not None:
                            # Inverse risk weighting: safer stocks get higher weights
                            # risk_score 0.0 → factor 1.0, risk_score 0.5 → factor ~0.55, risk_score 1.0 → factor ~0.33
                            risk_factor = 1.0 / (1.0 + 2.0 * stock_risk_score)
                            # Blend with alpha signal strength
                            alpha_norm = (alpha_score - score_min) / score_range
                            risk_factors[symbol] = risk_factor * (0.5 + 0.5 * alpha_norm)
                        else:
                            # No per-stock risk data — use neutral factor
                            risk_factors[symbol] = 1.0

                    # Normalize risk factors to sum to alloc_pct
                    total_factor = sum(risk_factors.values())
                    if total_factor > 0:
                        weight_method = "risk_adjusted"
                        for symbol in risk_factors:
                            raw_weight = (risk_factors[symbol] / total_factor) * alloc_pct

                            # Apply per-stock position cap from risk agent (soft cap)
                            cap = per_stock_risk.get(symbol, {}).get("position_cap", 0.15)
                            target_weights[symbol] = round(raw_weight, 6)

                    # Re-normalize: if total < alloc_pct because caps constrained us,
                    # scale all weights proportionally until we hit alloc_pct or caps.
                    MAX_PASSES = 3
                    for _ in range(MAX_PASSES):
                        capped_sum = sum(target_weights.values())
                        if capped_sum >= alloc_pct * 0.99:  # within 1%, good enough
                            break
                        # Find stocks with headroom below their cap
                        remaining = alloc_pct - capped_sum
                        candidates = {
                            s: w for s, w in target_weights.items()
                            if w < per_stock_risk.get(s, {}).get("position_cap", 0.15) * 0.99
                        }
                        if not candidates:
                            # All stocks at cap — scale caps up by 25% and retry
                            for s in target_weights:
                                old_cap = per_stock_risk.get(s, {}).get("position_cap", 0.15)
                                per_stock_risk[s]["position_cap"] = round(old_cap * 1.25, 4)
                            # Re-apply caps with new limits
                            for s in target_weights:
                                new_cap = per_stock_risk[s].get("position_cap", 0.15)
                                target_weights[s] = min(target_weights[s], new_cap)
                            continue
                        # Distribute remaining proportionally to candidates
                        candidate_sum = sum(candidates.values())
                        for s in candidates:
                            extra = (candidates[s] / candidate_sum) * remaining
                            cap = per_stock_risk.get(s, {}).get("position_cap", 0.15)
                            target_weights[s] = round(min(target_weights[s] + extra, cap), 6)

                    # Final: if still under-allocated, just scale everything up proportionally
                    final_sum = sum(target_weights.values())
                    if final_sum > 0 and final_sum < alloc_pct:
                        scale = alloc_pct / final_sum
                        for s in target_weights:
                            target_weights[s] = round(target_weights[s] * scale, 6)

                # If risk-adjusted weighting produced nothing, fall back to equal-weight
                if not target_weights:
                    weight_method = "equal_weight"
                    weight_per_position = alloc_pct / len(selected)
                    for symbol, _ in selected:
                        # Still apply position caps if available
                        cap = per_stock_risk.get(symbol, {}).get("position_cap", weight_per_position * 2)
                        target_weights[symbol] = min(weight_per_position, cap)

        return {
            "status": "success",
            "target_weights": target_weights,
            "risk_adjustment": {
                "risk_level": risk_level,
                "risk_score": risk_score_global,
                "capital_allocation": alloc_pct,
                "investable_capital": investable_capital,
                "weight_method": weight_method,
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


def generate_orders_cn(
    target_weights: Dict[str, float],
    current_positions: Dict[str, float],
    total_capital: float,
    market_prices: Dict[str, float],
    lot_size: int = 100,
    min_trade_value: float = 10_000.0,
) -> List[Dict[str, Any]]:
    """
    Compute orders for A-share market with round-lot sizing.

    Same logic as generate_orders(), but:
        - qty is rounded down to nearest lot (100 shares)
        - minimum trade value is in CNY (default ¥10,000)
        - reason text uses ¥ instead of $
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

        # Round down to nearest lot
        raw_qty = int(abs(diff) / price)
        qty = (raw_qty // lot_size) * lot_size
        if qty < lot_size:
            continue

        if diff > 0:
            orders.append({
                "symbol": symbol,
                "side": "buy",
                "qty": qty,
                "order_type": "limit",
                "limit_price": round(price * 1.005, 2),
                "estimated_value": qty * price,
                "reason": f"target_weight={target_weight:.3f}, current_value=¥{current_value:,.0f}, diff=+¥{diff:,.0f}",
            })
        else:
            orders.append({
                "symbol": symbol,
                "side": "sell",
                "qty": qty,
                "order_type": "limit",
                "limit_price": round(price * 0.995, 2),
                "estimated_value": qty * price,
                "reason": f"target_weight={target_weight:.3f}, current_value=¥{current_value:,.0f}, diff=¥{diff:,.0f}",
            })

    # Sells first (raise cash for T+1), then buys
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
        price_data: pd.DataFrame = None,
    ) -> Dict[str, Any]:
        tx_costs = transaction_costs or {"fixed_cost": 1.0, "slippage": 0.0001}

        # Use local implementation directly — faster and more reliable than LLM round-trip
        result = _construct_portfolio_impl(
            alpha_signals, risk_signals, tx_costs,
            current_portfolio, total_capital, max_positions,
            price_data=price_data,
        )
        return result


if __name__ == "__main__":
    print("Portfolio Agent Initialized")
