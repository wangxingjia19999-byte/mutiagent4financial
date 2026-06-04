"""
Risk Signal Agent — Multi-Dimensional Risk Analysis

Assesses risk at two levels:
  1. Portfolio-level  — market regime, correlation, concentration, composite risk score
  2. Per-stock         — volatility, drawdown, beta, VaR/CVaR, position caps

Integrates with Portfolio Agent via per-stock risk scores that drive position sizing,
and with the Orchestrator via overall_risk_level for capital allocation decisions.

Architecture:
  - Quantitative metrics always run locally (fast, deterministic)
  - LLM adds qualitative narrative + risk-event commentary when available
  - Degrades gracefully: if LLM fails, quantitative results still flow through
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger("RiskSignalAgent")


def _llm_runtime_supported() -> bool:
    if os.getenv("RISK_AGENT_DISABLE_LLM", "").lower() in {"1", "true", "yes"}:
        return False
    major, minor = sys.version_info[:2]
    return (major, minor) < (3, 14)


project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from agent_pools.poe_config import setup_poe_env, resolve_poe_model

setup_poe_env()

parent_dir = Path(__file__).parent.parent
alpha_agent_pool_path = parent_dir / "alpha_agent_pool"

import nest_asyncio
nest_asyncio.apply()
sys.path.append(str(alpha_agent_pool_path))
from local_agents import Agent, function_tool

# Optional Qlib imports (fallback to dataclass stubs)
try:
    qlib_path = alpha_agent_pool_path / "qlib_local"
    if not qlib_path.exists():
        qlib_path = alpha_agent_pool_path / "qlib"
    sys.path.insert(0, str(qlib_path))
    from utils import QlibConfig, DataProcessor
except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class QlibConfig:
        provider_uri: str = ""
        instruments: List[str] = field(default_factory=list)

    class DataProcessor:
        def __init__(self, config):
            self.config = config

        def add_returns(self, data):
            return data


# ══════════════════════════════════════════════════════════════════════════════
# Per-Stock Risk Metrics
# ══════════════════════════════════════════════════════════════════════════════

def _compute_returns(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize columns and compute daily log returns per symbol."""
    df = data.copy()
    if isinstance(df.index, pd.MultiIndex):
        df = df.reset_index()

    col_map = {c: c.lower() for c in df.columns}
    df = df.rename(columns=col_map)
    if 'instrument' in df.columns:
        df = df.rename(columns={'instrument': 'symbol'})
    if 'datetime' in df.columns:
        df = df.rename(columns={'datetime': 'date'})

    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)

    if 'close' not in df.columns:
        raise ValueError("DataFrame must contain a 'close' column")

    if 'symbol' in df.columns:
        df = df.sort_values(['symbol', 'date'])
        df['return'] = df.groupby('symbol')['close'].transform(
            lambda x: x.pct_change()
        )
    else:
        df = df.sort_values('date')
        df['return'] = df['close'].pct_change()

    return df.dropna(subset=['return'])


def _per_stock_volatility(df: pd.DataFrame, window: int = 20) -> Dict[str, Dict[str, float]]:
    """Annualized volatility per symbol."""
    result = {}
    grouped = df.groupby('symbol') if 'symbol' in df.columns else [('_market', df)]
    for sym, grp in grouped:
        rets = grp['return'].dropna()
        if len(rets) < window:
            result[sym] = {"volatility": 0.0, "volatility_short": 0.0, "n_obs": len(rets)}
            continue
        vol_long = float(rets.rolling(window=min(window, len(rets))).std().iloc[-1] * np.sqrt(252))
        vol_short = float(rets.tail(min(10, len(rets))).std() * np.sqrt(252))
        result[sym] = {
            "volatility": round(vol_long, 6),
            "volatility_short": round(vol_short, 6),
            "n_obs": len(rets),
        }
    return result


def _per_stock_drawdown(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Max drawdown and current drawdown per symbol."""
    result = {}
    grouped = df.groupby('symbol') if 'symbol' in df.columns else [('_market', df)]
    for sym, grp in grouped:
        cum = (1 + grp['return'].dropna()).cumprod()
        if len(cum) < 2:
            result[sym] = {"max_drawdown": 0.0, "current_drawdown": 0.0}
            continue
        running_max = cum.cummax()
        drawdown = (cum - running_max) / running_max
        result[sym] = {
            "max_drawdown": round(float(drawdown.min()), 6),
            "current_drawdown": round(float(drawdown.iloc[-1]), 6),
        }
    return result


def _per_stock_var_cvar(df: pd.DataFrame, confidence: float = 0.05) -> Dict[str, Dict[str, float]]:
    """Historical VaR and CVaR (Expected Shortfall) at given confidence."""
    result = {}
    grouped = df.groupby('symbol') if 'symbol' in df.columns else [('_market', df)]
    for sym, grp in grouped:
        rets = grp['return'].dropna()
        if len(rets) < 20:
            result[sym] = {"var_95": 0.0, "cvar_95": 0.0, "n_obs": len(rets)}
            continue
        var_val = float(np.percentile(rets, confidence * 100))
        tail = rets[rets <= var_val]
        cvar_val = float(tail.mean()) if len(tail) > 0 else var_val
        result[sym] = {
            "var_95": round(var_val, 6),
            "cvar_95": round(cvar_val, 6),
            "n_obs": len(rets),
        }
    return result


def _per_stock_beta(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Beta of each stock vs the equal-weight portfolio (market proxy)."""
    result = {}
    if 'symbol' not in df.columns:
        return {"_market": {"beta": 1.0, "r_squared": 1.0}}

    # Build equal-weight market return
    market_ret = df.groupby('date')['return'].mean().rename('market_return')
    market_df = market_ret.reset_index()

    for sym, grp in df.groupby('symbol'):
        merged = grp[['date', 'return']].merge(market_df, on='date').dropna()
        if len(merged) < 10:
            result[sym] = {"beta": 1.0, "r_squared": 0.0, "n_obs": len(merged)}
            continue
        cov = np.cov(merged['return'], merged['market_return'])
        beta_val = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 1.0
        corr = np.corrcoef(merged['return'], merged['market_return'])[0, 1]
        result[sym] = {
            "beta": round(beta_val, 4),
            "r_squared": round(corr ** 2, 4) if not np.isnan(corr) else 0.0,
            "n_obs": len(merged),
        }
    return result


def _per_stock_sharpe_sortino(df: pd.DataFrame, rf_annual: float = 0.03) -> Dict[str, Dict[str, float]]:
    """Sharpe ratio and Sortino ratio (annualized) per symbol."""
    rf_daily = rf_annual / 252
    result = {}
    grouped = df.groupby('symbol') if 'symbol' in df.columns else [('_market', df)]
    for sym, grp in grouped:
        rets = grp['return'].dropna()
        if len(rets) < 10 or rets.std() == 0:
            result[sym] = {"sharpe": 0.0, "sortino": 0.0, "n_obs": len(rets)}
            continue
        excess = rets - rf_daily
        sharpe = float(excess.mean() / rets.std() * np.sqrt(252))
        downside = rets[rets < 0]
        if len(downside) < 3 or downside.std() == 0:
            sortino = sharpe
        else:
            sortino = float(excess.mean() / downside.std() * np.sqrt(252))
        result[sym] = {
            "sharpe": round(sharpe, 4),
            "sortino": round(sortino, 4),
            "n_obs": len(rets),
        }
    return result


def _per_stock_liquidity(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Liquidity risk: avg daily volume, volume CV, Amihud illiquidity."""
    result = {}
    if 'volume' not in df.columns:
        return result

    grouped = df.groupby('symbol') if 'symbol' in df.columns else [('_market', df)]
    for sym, grp in grouped:
        vol = grp['volume'].dropna()
        if len(vol) < 5:
            result[sym] = {"avg_volume": 0.0, "volume_cv": 0.0, "amihud": 0.0}
            continue
        avg_vol = float(vol.mean())
        vol_cv = float(vol.std() / avg_vol) if avg_vol > 0 else 0.0
        # Amihud illiquidity: avg(|return| / dollar_volume), scaled up for readability
        grp_copy = grp.copy()
        grp_copy['dollar_vol'] = grp_copy['close'] * grp_copy['volume']
        grp_copy['abs_ret'] = grp_copy['return'].abs()
        valid = grp_copy[grp_copy['dollar_vol'] > 0]
        amihud = float((valid['abs_ret'] / valid['dollar_vol']).mean() * 1e8) if len(valid) > 0 else 0.0
        result[sym] = {
            "avg_volume": round(avg_vol, 0),
            "volume_cv": round(vol_cv, 4),
            "amihud": round(amihud, 6),
        }
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Portfolio-Level Risk Metrics
# ══════════════════════════════════════════════════════════════════════════════

def _portfolio_correlation(df: pd.DataFrame) -> Dict[str, float]:
    """Average pairwise correlation among stocks."""
    if 'symbol' not in df.columns:
        return {"avg_correlation": 0.0, "n_pairs": 0}

    pivot = df.pivot_table(index='date', columns='symbol', values='return', aggfunc='mean')
    pivot = pivot.dropna(axis=1, thresh=int(len(pivot) * 0.5))  # require 50% coverage
    if pivot.shape[1] < 2:
        return {"avg_correlation": 0.0, "n_pairs": 0}

    corr_matrix = pivot.corr()
    # Extract upper triangle (excluding diagonal)
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    values = upper.stack().dropna()
    return {
        "avg_correlation": round(float(values.mean()), 4) if len(values) > 0 else 0.0,
        "max_correlation": round(float(values.max()), 4) if len(values) > 0 else 0.0,
        "n_pairs": len(values),
    }


def _portfolio_concentration(target_weights: Optional[Dict[str, float]] = None,
                              n_stocks: int = 1) -> Dict[str, float]:
    """Herfindahl-Hirschman Index (HHI) for concentration risk."""
    if target_weights:
        hhi = sum(w ** 2 for w in target_weights.values())
        effective_n = int(1.0 / hhi) if hhi > 0 else len(target_weights)
        return {"hhi": round(hhi, 6), "effective_n": effective_n, "n_assets": len(target_weights)}
    else:
        return {"hhi": round(1.0 / n_stocks, 6), "effective_n": n_stocks, "n_assets": n_stocks}


def _market_regime(df: pd.DataFrame) -> Dict[str, Any]:
    """Detect market regime: trending-bull, trending-bear, ranging, high-vol."""
    if 'symbol' not in df.columns:
        rets = df['return'].dropna()
    else:
        rets = df.groupby('date')['return'].mean().dropna()

    if len(rets) < 20:
        return {"regime": "unknown", "confidence": 0.0}

    # Trend strength: ratio of |cumulative return| to sum of |daily returns|
    cum_ret = (1 + rets).prod() - 1
    summed_abs = rets.abs().sum()
    trend_strength = abs(cum_ret) / summed_abs if summed_abs > 0 else 0

    # Volatility regime
    recent_vol = float(rets.tail(20).std() * np.sqrt(252))
    long_vol = float(rets.std() * np.sqrt(252))
    vol_ratio = recent_vol / long_vol if long_vol > 0 else 1.0

    # Recent return direction
    recent_ret = float(rets.tail(20).mean() * 252)

    if vol_ratio > 1.5:
        regime = "high_volatility"
        confidence = min(vol_ratio / 3.0, 1.0)
    elif trend_strength > 0.15:
        regime = "trending_bull" if cum_ret > 0 else "trending_bear"
        confidence = min(trend_strength / 0.3, 1.0)
    elif trend_strength > 0.05:
        regime = "weak_trend"
        confidence = trend_strength / 0.15
    else:
        regime = "ranging"
        confidence = 1.0 - min(trend_strength / 0.05, 1.0)

    return {
        "regime": regime,
        "confidence": round(confidence, 4),
        "trend_strength": round(trend_strength, 4),
        "vol_ratio": round(vol_ratio, 4),
        "recent_annual_return": round(recent_ret, 4),
        "cumulative_return": round(cum_ret, 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Composite Risk Scoring
# ══════════════════════════════════════════════════════════════════════════════

def _normalize_risk(value: float, low: float, high: float, invert: bool = False) -> float:
    """Map a metric value to [0, 1] risk score. Invert for metrics where higher = safer."""
    if high == low:
        return 0.5
    score = (value - low) / (high - low)
    score = max(0.0, min(1.0, score))
    return 1.0 - score if invert else score


def _compute_composite_risk_score(
    portfolio_vol: float,
    portfolio_var: float,
    max_drawdown: float,
    avg_correlation: float,
    hhi: float,
    vol_ratio: float,
) -> float:
    """
    Weighted composite risk score (0–1, higher = riskier).
    Weights calibrated so that each dimension contributes meaningfully.
    """
    components = [
        (_normalize_risk(portfolio_vol, 0.08, 0.45), 0.20),       # Vol: 8%–45% annual
        (_normalize_risk(abs(portfolio_var), 0.005, 0.06), 0.20), # VaR magnitude
        (_normalize_risk(abs(max_drawdown), 0.02, 0.40), 0.20),    # Drawdown
        (_normalize_risk(avg_correlation, 0.05, 0.70), 0.15),     # Correlation
        (_normalize_risk(hhi, 0.02, 0.30), 0.10),                  # Concentration
        (_normalize_risk(vol_ratio, 0.70, 2.50), 0.15),           # Vol regime shift
    ]
    score = sum(s * w for s, w in components)
    return round(score, 4)


def _score_to_risk_level(score: float) -> str:
    """Map continuous risk score to discrete level — all three levels reachable."""
    if score < 0.30:
        return "LOW"
    elif score < 0.60:
        return "MODERATE"
    else:
        return "HIGH"


def _per_stock_risk_assessment(
    df: pd.DataFrame,
    portfolio_vol: float,
    portfolio_risk_level: str = "LOW",
) -> Dict[str, Dict[str, Any]]:
    """
    Assemble per-stock risk profiles and assign position caps.
    Lower-risk stocks get higher caps; high-risk stocks get constrained.
    """
    vol_data = _per_stock_volatility(df)
    dd_data = _per_stock_drawdown(df)
    var_data = _per_stock_var_cvar(df)
    beta_data = _per_stock_beta(df)
    sharpe_data = _per_stock_sharpe_sortino(df)
    liq_data = _per_stock_liquidity(df)

    symbols = set(list(vol_data.keys()) + list(dd_data.keys()) + list(var_data.keys()))

    result = {}
    for sym in symbols:
        v = vol_data.get(sym, {})
        d = dd_data.get(sym, {})
        var = var_data.get(sym, {})
        beta = beta_data.get(sym, {})
        sh = sharpe_data.get(sym, {})
        liq = liq_data.get(sym, {})

        stock_vol = v.get("volatility", 0.0)
        stock_dd = abs(d.get("max_drawdown", 0.0))
        stock_beta = beta.get("beta", 1.0)
        stock_var = abs(var.get("var_95", 0.0))

        # Per-stock composite risk score
        stock_score = (
            _normalize_risk(stock_vol, 0.10, 0.55) * 0.25 +
            _normalize_risk(stock_dd, 0.03, 0.50) * 0.25 +
            _normalize_risk(stock_beta, 0.3, 2.5) * 0.25 +
            _normalize_risk(stock_var, 0.008, 0.07) * 0.25
        )
        stock_score = round(stock_score, 4)

        # Position cap: riskier stocks get smaller max allocation.
        # Caps scale with portfolio risk level — tighter when overall risk is high.
        if portfolio_risk_level == "HIGH":
            cap_tiers = [0.06, 0.04, 0.03, 0.02]
        elif portfolio_risk_level == "MODERATE":
            cap_tiers = [0.10, 0.07, 0.05, 0.03]
        else:  # LOW
            cap_tiers = [0.18, 0.12, 0.08, 0.05]

        if stock_score < 0.25:
            position_cap = cap_tiers[0]
        elif stock_score < 0.45:
            position_cap = cap_tiers[1]
        elif stock_score < 0.65:
            position_cap = cap_tiers[2]
        else:
            position_cap = cap_tiers[3]

        result[sym] = {
            "volatility": stock_vol,
            "volatility_short": v.get("volatility_short", 0.0),
            "max_drawdown": d.get("max_drawdown", 0.0),
            "current_drawdown": d.get("current_drawdown", 0.0),
            "beta": stock_beta,
            "var_95": var.get("var_95", 0.0),
            "cvar_95": var.get("cvar_95", 0.0),
            "sharpe": sh.get("sharpe", 0.0),
            "sortino": sh.get("sortino", 0.0),
            "risk_score": stock_score,
            "risk_level": _score_to_risk_level(stock_score * 1.3),  # tighter threshold for individual
            "position_cap": position_cap,
            "avg_volume": liq.get("avg_volume", 0.0),
            "amihud": liq.get("amihud", 0.0),
        }

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Core Pipeline Implementation
# ══════════════════════════════════════════════════════════════════════════════

def _run_risk_pipeline_impl(
    data: pd.DataFrame,
    market_returns: Optional[pd.Series] = None,
    metrics: Optional[List[str]] = None,
    processor: Any = None,
    current_portfolio: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Full multi-dimensional risk pipeline.

    Args:
        data: DataFrame with columns [date, symbol, open, high, low, close, volume]
        market_returns: optional external market benchmark returns
        metrics: which metric groups to compute (all if None)
        processor: optional DataProcessor instance
        current_portfolio: optional current portfolio weights for concentration check

    Returns:
        Dict with portfolio-level + per-stock risk metrics
    """
    metrics = metrics or ['volatility', 'var', 'drawdown', 'correlation', 'regime']
    result: Dict[str, Any] = {"status": "success"}

    try:
        # ── Prepare data ──
        df = _compute_returns(data)
        n_observations = int(len(df))
        n_symbols = len(df['symbol'].unique()) if 'symbol' in df.columns else 1

        # ── Aggregate portfolio return series ──
        if 'symbol' in df.columns:
            portfolio_rets = df.groupby('date')['return'].mean().dropna()
        else:
            portfolio_rets = df['return'].dropna()

        # ── Portfolio-level metrics ──
        risk_metrics: Dict[str, Any] = {}

        # 1. Volatility
        if 'volatility' in metrics:
            vol = float(portfolio_rets.std() * np.sqrt(252))
            vol_short = float(portfolio_rets.tail(20).std() * np.sqrt(252)) if len(portfolio_rets) >= 20 else vol
            risk_metrics['volatility'] = {
                "current": round(vol, 6),
                "short_term": round(vol_short, 6),
            }

        # 2. VaR & CVaR
        if 'var' in metrics and len(portfolio_rets) >= 20:
            var_95 = float(np.percentile(portfolio_rets, 5))
            tail = portfolio_rets[portfolio_rets <= var_95]
            cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95
            risk_metrics['var'] = {
                "historical_var_95": round(var_95, 6),
                "historical_cvar_95": round(cvar_95, 6),
            }

        # 3. Drawdown
        if 'drawdown' in metrics and len(portfolio_rets) >= 2:
            cum = (1 + portfolio_rets).cumprod()
            running_max = cum.cummax()
            dd_series = (cum - running_max) / running_max
            risk_metrics['drawdown'] = {
                "max_drawdown": round(float(dd_series.min()), 6),
                "current_drawdown": round(float(dd_series.iloc[-1]), 6),
            }

        # 4. Correlation
        if 'correlation' in metrics:
            corr_data = _portfolio_correlation(df)
            risk_metrics['correlation'] = corr_data

        # 5. Market regime
        regime_data = _market_regime(df) if 'regime' in metrics else {"regime": "unknown", "confidence": 0.0}
        risk_metrics['regime'] = regime_data

        # 6. Concentration
        conc_data = _portfolio_concentration(current_portfolio, n_symbols)
        risk_metrics['concentration'] = conc_data

        result['risk_metrics'] = risk_metrics

        # ── Composite risk score ──
        portfolio_vol = risk_metrics.get('volatility', {}).get('current', 0.15)
        portfolio_var = risk_metrics.get('var', {}).get('historical_var_95', -0.02)
        max_dd = risk_metrics.get('drawdown', {}).get('max_drawdown', -0.10)
        avg_corr = risk_metrics.get('correlation', {}).get('avg_correlation', 0.20)
        hhi = risk_metrics.get('concentration', {}).get('hhi', 0.05)
        vol_ratio = regime_data.get('vol_ratio', 1.0)

        composite_score = _compute_composite_risk_score(
            portfolio_vol, portfolio_var, max_dd, avg_corr, hhi, vol_ratio
        )
        risk_level = _score_to_risk_level(composite_score)

        result['risk_score'] = composite_score
        result['overall_risk_level'] = risk_level
        result['market_regime'] = regime_data.get('regime', 'unknown')

        # ── Legacy risk_signals (backward compat) ──
        result['risk_signals'] = {
            "volatility": "HIGH" if portfolio_vol > 0.30 else "LOW",
            "var": "HIGH" if abs(portfolio_var) > 0.03 else "LOW",
            "drawdown": "HIGH" if abs(max_dd) > 0.20 else "LOW",
        }

        # ── Per-stock risk profiles ──
        result['per_stock_risk'] = _per_stock_risk_assessment(df, portfolio_vol, risk_level)

        result['n_observations'] = n_observations
        result['n_symbols'] = n_symbols

        return result

    except Exception as e:
        logger.error("Risk pipeline failed: %s", e)
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# LLM Risk Narrative Generator
# ══════════════════════════════════════════════════════════════════════════════

def _build_risk_narrative_prompt(risk_data: Dict[str, Any]) -> str:
    """Build a concise prompt for the LLM to generate a risk narrative."""
    score = risk_data.get('risk_score', 0.0)
    level = risk_data.get('overall_risk_level', 'UNKNOWN')
    regime = risk_data.get('market_regime', 'unknown')
    metrics = risk_data.get('risk_metrics', {})
    per_stock = risk_data.get('per_stock_risk', {})

    # Summarize per-stock risk: top 3 riskiest
    risky_stocks = sorted(
        per_stock.items(),
        key=lambda x: x[1].get('risk_score', 0), reverse=True
    )[:5]
    stock_summary = "\n".join(
        f"  {sym}: risk={info.get('risk_score', '?')}, vol={info.get('volatility', '?')}, "
        f"beta={info.get('beta', '?')}, maxDD={info.get('max_drawdown', '?')}"
        for sym, info in risky_stocks
    ) if risky_stocks else "  (no stock-level data)"

    prompt = f"""You are a senior risk analyst. Review these metrics and write a 3-4 sentence risk narrative.

Risk Level: {level} (score={score})
Market Regime: {regime}
Portfolio Metrics:
  Annualized Vol: {metrics.get('volatility', {}).get('current', 'N/A')}
  Short-term Vol: {metrics.get('volatility', {}).get('short_term', 'N/A')}
  VaR 95%: {metrics.get('var', {}).get('historical_var_95', 'N/A')}
  CVaR 95%: {metrics.get('var', {}).get('historical_cvar_95', 'N/A')}
  Max Drawdown: {metrics.get('drawdown', {}).get('max_drawdown', 'N/A')}
  Avg Correlation: {metrics.get('correlation', {}).get('avg_correlation', 'N/A')}
  Concentration HHI: {metrics.get('concentration', {}).get('hhi', 'N/A')}

Highest-risk stocks:
{stock_summary}

Respond in Chinese (since this is a Chinese quant system). Keep it concise — 3 to 4 sentences max.
Cover: (1) overall risk assessment, (2) key risk driver, (3) one actionable suggestion."""

    return prompt


def _generate_llm_risk_narrative(
    risk_data: Dict[str, Any],
    model: str,
    agent: Agent,
) -> Dict[str, Any]:
    """Attempt to enrich risk results with LLM-generated narrative."""
    if not _llm_runtime_supported():
        return {"llm_used": False, "reason": "runtime not supported"}

    try:
        prompt = _build_risk_narrative_prompt(risk_data)
        context = {"narrative_prompt": prompt}
        agent.run("Generate risk narrative.", context=context, max_turns=3)
        narrative = context.get("narrative", context.get("result", ""))
        if isinstance(narrative, dict):
            narrative = narrative.get("message", str(narrative))
        return {"llm_used": True, "risk_narrative": str(narrative)[:800]}
    except Exception as e:
        logger.warning("LLM risk narrative generation failed: %s", e)
        return {"llm_used": False, "reason": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# Tools (LLM function-calling interface)
# ══════════════════════════════════════════════════════════════════════════════

@function_tool
def run_risk_pipeline(ctx: dict) -> str:
    """Execute the full multi-dimensional risk pipeline and store results in context."""
    logger.debug("run_risk_pipeline (Macro) INVOKED")
    try:
        data = ctx.get('data')
        if data is None:
            return "Error: No data in context."

        metrics = ctx.get('risk_metrics', None)
        result = _run_risk_pipeline_impl(data, None, metrics, None, ctx.get('current_portfolio'))

        ctx['result'] = result
        ctx['risk_result'] = result

        n_stocks = result.get('n_symbols', 0)
        level = result.get('overall_risk_level', '?')
        score = result.get('risk_score', '?')
        regime = result.get('market_regime', '?')

        # Build summary of risky stocks
        per_stock = result.get('per_stock_risk', {})
        high_risk = [s for s, r in per_stock.items() if r.get('risk_level') == 'HIGH']
        warn = f" ⚠️ {len(high_risk)} high-risk stocks: {', '.join(high_risk[:5])}" if high_risk else ""

        return (
            f"Risk analysis complete. Level={level} (score={score:.3f}), "
            f"Regime={regime}, Stocks={n_stocks}.{warn}"
        )
    except Exception as e:
        return f"Error: {e}"


@function_tool
def calculate_volatility_tool(ctx: dict, window: int = 20) -> str:
    """Calculate per-stock and portfolio volatility. Stores in ctx.risk_metrics."""
    logger.debug("calculate_volatility_tool INVOKED")
    try:
        data = ctx.get('data')
        if data is None:
            return "Error: No data."

        df = _compute_returns(data)
        per_stock = _per_stock_volatility(df, window)

        # Portfolio aggregate
        if 'symbol' in df.columns:
            port_rets = df.groupby('date')['return'].mean().dropna()
        else:
            port_rets = df['return'].dropna()
        port_vol = float(port_rets.std() * np.sqrt(252))

        if 'risk_metrics' not in ctx:
            ctx['risk_metrics'] = {}
        ctx['risk_metrics']['volatility'] = {"current": port_vol}
        ctx['risk_metrics']['per_stock_volatility'] = per_stock

        return f"Volatility calculated: portfolio={port_vol:.4f}, stocks={len(per_stock)}."
    except Exception as e:
        return f"Error: {e}"


@function_tool
def generate_risk_narrative_tool(ctx: dict) -> str:
    """Generate LLM risk narrative from the metrics already in context."""
    logger.debug("generate_risk_narrative_tool INVOKED")
    try:
        risk_data = ctx.get('risk_result', ctx.get('result', {}))
        if not risk_data:
            return "Error: No risk data — run run_risk_pipeline first."

        prompt = _build_risk_narrative_prompt(risk_data)
        # Store prompt so agent can respond to it
        ctx['narrative_prompt'] = prompt
        ctx['narrative_requested'] = True
        return f"Narrative prompt ready. Please review the following and write a concise risk assessment:\n\n{prompt}"
    except Exception as e:
        return f"Error: {e}"


@function_tool
def submit_risk_assessment_tool(ctx: dict) -> str:
    """Submit final risk assessment from metrics accumulated in context."""
    logger.debug("submit_risk_assessment_tool INVOKED")
    try:
        metrics = ctx.get('risk_metrics', {})
        if not metrics:
            return "Error: No risk metrics accumulated."

        # Build a minimal result from accumulated metrics
        port_vol = metrics.get('volatility', {}).get('current', 0.0)
        port_var = metrics.get('var', {}).get('historical_var_95', 0.0)

        risk_signals = {}
        if port_vol > 0.30:
            risk_signals['volatility'] = 'HIGH'
        else:
            risk_signals['volatility'] = 'LOW'
        if abs(port_var) > 0.03:
            risk_signals['var'] = 'HIGH'
        else:
            risk_signals['var'] = 'LOW'

        score = 0.0
        if risk_signals.get('volatility') == 'HIGH':
            score += 0.5
        if risk_signals.get('var') == 'HIGH':
            score += 0.5
        level = "HIGH" if score >= 0.5 else "LOW"

        result = {
            "status": "success",
            "risk_metrics": metrics,
            "risk_signals": risk_signals,
            "overall_risk_level": level,
            "risk_score": score,
        }
        ctx['result'] = result
        return f"Risk assessment submitted. Level={level}."
    except Exception as e:
        return f"Error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# Risk Agent Class
# ══════════════════════════════════════════════════════════════════════════════

class RiskSignalAgent:
    """
    Multi-dimensional risk agent that assesses both portfolio-level and per-stock risk.

    Key outputs:
      - overall_risk_level:  LOW / MODERATE / HIGH  (continuous score → 3 tiers)
      - risk_score:          0–1 composite score from 6 weighted dimensions
      - market_regime:       trending_bull / trending_bear / high_volatility / ranging
      - per_stock_risk:      {symbol: {vol, drawdown, beta, var, sharpe, risk_level, position_cap}}
      - risk_narrative:      (optional) LLM-generated qualitative assessment
    """

    def __init__(
        self,
        name: str = "RiskSignalAgent",
        model: str = None,
        qlib_config: Optional[QlibConfig] = None,
        enable_llm_narrative: bool = True,
    ):
        self.name = name
        self.model = model or resolve_poe_model("openai/gpt-4o-mini")
        self.qlib_config = qlib_config or QlibConfig()
        self.data_processor = DataProcessor(self.qlib_config)
        self.enable_llm_narrative = enable_llm_narrative

        self.tools = [
            run_risk_pipeline,
            calculate_volatility_tool,
            generate_risk_narrative_tool,
            submit_risk_assessment_tool,
        ]

        self.agent = Agent(
            name=name,
            instructions="""You are a quantitative Risk Agent for a multi-asset trading system.

You have access to these tools:
- run_risk_pipeline: Run the FULL multi-dimensional risk pipeline (portfolio + per-stock). This is the RECOMMENDED path — it computes volatility, VaR/CVaR, drawdown, correlation, concentration, and market regime in one call.
- calculate_volatility_tool: Compute only volatility metrics (per-stock + portfolio).
- generate_risk_narrative_tool: Generate a natural-language risk assessment from existing metrics. Use AFTER run_risk_pipeline.
- submit_risk_assessment_tool: Finalize and submit the risk assessment.

STANDARD WORKFLOW:
1. Call run_risk_pipeline first (it does everything).
2. Optionally call generate_risk_narrative_tool for a qualitative summary.
3. The results are automatically stored in context — no need to call submit_risk_assessment_tool unless using the custom path.""",
            model=self.model,
            tools=self.tools,
        )

    def run(self, user_request: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.agent.run(user_request, context=context, max_turns=10)

    def generate_risk_signals_from_data(
        self,
        data: pd.DataFrame,
        market_returns: Optional[pd.Series] = None,
        risk_metrics: Optional[List[str]] = None,
        current_portfolio: Optional[Dict[str, float]] = None,
        enable_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Main entry point — called by Orchestrator.

        Args:
            data: OHLCV DataFrame with columns [date, symbol, open, high, low, close, volume]
            market_returns: optional benchmark return series
            risk_metrics: optional list of metric groups to compute
            current_portfolio: optional current portfolio weights
            enable_llm: whether to attempt LLM narrative generation

        Returns:
            Dict with status, overall_risk_level, risk_score, market_regime,
            per_stock_risk, risk_metrics, risk_signals, risk_narrative (if LLM enabled)
        """
        # ── Always run local pipeline (fast, deterministic) ──
        result = _run_risk_pipeline_impl(
            data=data,
            market_returns=market_returns,
            metrics=risk_metrics,
            processor=self.data_processor,
            current_portfolio=current_portfolio,
        )

        if result.get("status") != "success":
            return result

        # ── Optionally enrich with LLM narrative ──
        if enable_llm and self.enable_llm_narrative:
            if not _llm_runtime_supported():
                logger.info("LLM runtime not supported — skipping risk narrative.")
                result['risk_narrative'] = _fallback_narrative(result)
            else:
                try:
                    llm_result = _generate_llm_risk_narrative(result, self.model, self.agent)
                    if llm_result.get("llm_used"):
                        result['risk_narrative'] = llm_result.get("risk_narrative", "")
                        result['llm_narrative_used'] = True
                    else:
                        result['risk_narrative'] = _fallback_narrative(result)
                        result['llm_narrative_used'] = False
                except Exception as e:
                    logger.warning("LLM narrative failed: %s — using fallback.", e)
                    result['risk_narrative'] = _fallback_narrative(result)
                    result['llm_narrative_used'] = False

        return result


def _fallback_narrative(result: Dict[str, Any]) -> str:
    """Generate a rule-based risk narrative when LLM is unavailable."""
    level = result.get('overall_risk_level', 'UNKNOWN')
    regime = result.get('market_regime', 'unknown')
    score = result.get('risk_score', 0.0)
    metrics = result.get('risk_metrics', {})

    vol = metrics.get('volatility', {}).get('current', 0)
    corr = metrics.get('correlation', {}).get('avg_correlation', 0)
    dd = metrics.get('drawdown', {}).get('max_drawdown', 0)
    n_stocks = result.get('n_symbols', 0)

    # Count risky stocks
    per_stock = result.get('per_stock_risk', {})
    high_risk_count = sum(1 for r in per_stock.values() if r.get('risk_level') == 'HIGH')

    sentences = []
    sentences.append(f"当前市场风险等级为{level}（综合评分{score:.2f}），市场处于{regime}状态。")

    if abs(dd) > 0.15:
        sentences.append(f"组合最大回撤{dd:.1%}，处于较高水平，建议降低仓位或增加对冲。")
    if corr > 0.5:
        sentences.append(f"股票间平均相关性{corr:.2f}偏高，分散化效果减弱，集中风险上升。")
    if high_risk_count > 0:
        sentences.append(f"{high_risk_count}/{n_stocks}只股票处于高风险状态，建议控制单只仓位上限。")
    if vol > 0.30:
        sentences.append(f"年化波动率{vol:.1%}较高，建议将总仓位降至50%-70%。")
    elif vol < 0.12:
        sentences.append(f"年化波动率{vol:.1%}较低，市场环境稳定，可维持正常仓位。")

    if len(sentences) == 1:
        sentences.append("各项风险指标均在正常范围内，未发现显著风险点。")

    return " ".join(sentences)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  Risk Signal Agent — Multi-Dimensional Risk Analysis")
    print("=" * 60)

    # Quick smoke test with mock data
    import numpy as np
    from datetime import datetime, timedelta

    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=252, freq='B')
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'META']

    rows = []
    for sym in symbols:
        # Generate correlated returns with different risk profiles
        base_ret = np.random.normal(0.0005, 0.015, len(dates))
        if sym == 'TSLA':
            stock_ret = base_ret * 2.0 + np.random.normal(0, 0.02, len(dates))  # High vol
        elif sym == 'AAPL':
            stock_ret = base_ret * 0.7 + np.random.normal(0, 0.006, len(dates))  # Low vol
        else:
            stock_ret = base_ret + np.random.normal(0, 0.01, len(dates))

        price = 100 * np.cumprod(1 + stock_ret)
        volume = np.random.randint(5000000, 50000000, len(dates))

        for i, d in enumerate(dates):
            rows.append({
                'date': d, 'symbol': sym,
                'open': price[i] * 0.99, 'high': price[i] * 1.02,
                'low': price[i] * 0.98, 'close': price[i],
                'volume': volume[i],
            })

    test_df = pd.DataFrame(rows)

    agent = RiskSignalAgent(enable_llm_narrative=False)
    result = agent.generate_risk_signals_from_data(
        test_df, enable_llm=False
    )

    print(f"\nStatus: {result.get('status')}")
    print(f"Risk Level: {result.get('overall_risk_level')}")
    print(f"Risk Score: {result.get('risk_score')}")
    print(f"Market Regime: {result.get('market_regime')}")
    print(f"Observations: {result.get('n_observations')} | Symbols: {result.get('n_symbols')}")

    print("\n--- Portfolio Metrics ---")
    for k, v in result.get('risk_metrics', {}).items():
        print(f"  {k}: {v}")

    print("\n--- Per-Stock Risk ---")
    for sym, risk in result.get('per_stock_risk', {}).items():
        print(f"  {sym}: score={risk['risk_score']:.3f}, level={risk['risk_level']}, "
              f"vol={risk['volatility']:.3f}, beta={risk['beta']:.2f}, "
              f"maxDD={risk['max_drawdown']:.3f}, cap={risk['position_cap']:.0%}")

    print(f"\n--- Risk Narrative ---")
    print(result.get('risk_narrative', 'N/A'))

    print("\nSmoke test complete.")
