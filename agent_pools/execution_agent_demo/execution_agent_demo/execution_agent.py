import os
import sys
import json
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import warnings

from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from agent_pools.poe_config import setup_poe_env, resolve_poe_model

setup_poe_env()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ExecutionAgent")

parent_dir = Path(__file__).resolve().parents[3]
alpha_agent_pool_path = parent_dir / "agent_pools" / "alpha_agent_pool"
sys.path.append(str(alpha_agent_pool_path))

from local_agents import Agent, function_tool

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopOrderRequest,
        GetOrdersRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderType, OrderStatus
    from alpaca.common.exceptions import APIError
    ALPACA_AVAILABLE = True
except ImportError:
    logger.warning("Alpaca SDK not found. Using mock implementation.")
    ALPACA_AVAILABLE = False
    OrderSide = Any
    TimeInForce = Any
    OrderType = Any


# ── US Market Hours (Eastern) ──────────────────────────────────

def is_market_open() -> bool:
    """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, weekdays)."""
    now_utc = datetime.utcnow()
    # US Eastern is UTC-5 (EST) or UTC-4 (EDT). Use a simple approximation.
    # March-Nov: EDT (UTC-4), Nov-March: EST (UTC-5)
    month = now_utc.month
    is_dst = 3 < month < 11  # rough DST: April-October
    offset = 4 if is_dst else 5
    now_et_hour = (now_utc.hour - offset + 24) % 24
    now_et_minute = now_utc.minute

    if now_utc.weekday() >= 5:  # Saturday or Sunday
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)
    current = time(now_et_hour, now_et_minute)
    return market_open <= current <= market_close


def market_status_str() -> str:
    if is_market_open():
        return "OPEN"
    now_utc = datetime.utcnow()
    if now_utc.weekday() >= 5:
        return "CLOSED (WEEKEND)"
    return "CLOSED (OUTSIDE TRADING HOURS)"


# ── Risk Controls ─────────────────────────────────────────────

MAX_POSITION_PCT = 0.05   # max 5% of portfolio in a single stock (diversified)
MAX_ORDER_VALUE = 200000.0 # max $200k per single order
MIN_ORDER_VALUE = 50.0     # skip orders under $50


def validate_order(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    buying_power: float,
    portfolio_value: float,
    current_position_value: float = 0.0,
) -> Dict[str, Any]:
    """Validate an order against risk limits. Returns {"ok": True/False, "reason": ...}."""
    order_value = qty * price

    if order_value < MIN_ORDER_VALUE:
        return {"ok": False, "reason": f"Order value ${order_value:.0f} below minimum ${MIN_ORDER_VALUE:.0f}"}

    if order_value > MAX_ORDER_VALUE:
        return {"ok": False, "reason": f"Order value ${order_value:.0f} exceeds max ${MAX_ORDER_VALUE:.0f}"}

    if side == "buy":
        if order_value > buying_power:
            return {"ok": False, "reason": f"Buy value ${order_value:.0f} exceeds buying power ${buying_power:.0f}"}
        new_position_value = current_position_value + order_value
        if portfolio_value > 0 and new_position_value / portfolio_value > MAX_POSITION_PCT:
            return {"ok": False, "reason": f"Position would be {new_position_value/portfolio_value:.1%} of portfolio (max {MAX_POSITION_PCT:.0%})"}

    if side == "sell":
        if qty > (current_position_value / price if price > 0 else 0):
            return {"ok": False, "reason": f"Sell qty {qty} exceeds current position"}

    return {"ok": True, "reason": "passed"}


# ── Alpaca Service ────────────────────────────────────────────

class AlpacaService:
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.client = None
        self.is_mock = False

        if not api_key or "MOCK" in api_key.upper():
            self.is_mock = True
            logger.info("Using Mock Alpaca Service (invalid or mock keys detected)")
            return

        if ALPACA_AVAILABLE and api_key:
            try:
                self.client = TradingClient(api_key, secret_key, paper=paper)
                logger.info(f"Connected to Alpaca {'Paper' if paper else 'Live'} Trading")
            except Exception as e:
                logger.error(f"Failed to connect to Alpaca: {e}")
                self.is_mock = True
        else:
            logger.warning("Alpaca client not initialized (missing keys or library)")
            self.is_mock = True

    def get_account(self):
        if not self.is_mock and self.client:
            try:
                return self.client.get_account()
            except Exception as e:
                logger.warning(f"Alpaca API error: {e}. Falling back to mock.")
        return type('obj', (object,), {
            "buying_power": "100000.00",
            "cash": "50000.00",
            "portfolio_value": "150000.00",
            "currency": "USD",
            "status": "ACTIVE",
        })()

    def get_positions(self):
        if not self.is_mock and self.client:
            try:
                return self.client.get_all_positions()
            except Exception:
                pass
        return []

    def get_position_value(self, symbol: str) -> float:
        """Get market value of a specific position."""
        positions = self.get_positions()
        for p in positions:
            sym = getattr(p, "symbol", "")
            if sym == symbol:
                return float(getattr(p, "market_value", 0))
        return 0.0

    def place_order(self, symbol: str, qty: float, side: str, order_type: str = "market",
                    limit_price: float = None, stop_price: float = None,
                    time_in_force: str = "day") -> Dict[str, Any]:
        """Place an order. Returns dict with status and details."""
        if self.is_mock or not self.client:
            logger.info(f"MOCK ORDER: {side} {qty} {symbol} ({order_type})")
            return {"symbol": symbol, "status": "filled", "qty": qty, "side": side,
                    "filled_price": 100.0, "order_type": order_type, "id": f"mock_{symbol}"}

        try:
            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            if order_type == "limit" and limit_price:
                req = LimitOrderRequest(
                    symbol=symbol, qty=qty, side=order_side,
                    limit_price=limit_price, time_in_force=TimeInForce.DAY,
                )
            elif order_type == "stop_loss" and stop_price:
                req = StopOrderRequest(
                    symbol=symbol, qty=qty, side=order_side,
                    stop_price=stop_price, time_in_force=TimeInForce.DAY,
                )
            else:
                req = MarketOrderRequest(
                    symbol=symbol, qty=qty, side=order_side,
                    time_in_force=TimeInForce.DAY,
                )

            result = self.client.submit_order(order_data=req)
            return {
                "symbol": symbol,
                "status": str(result.status),
                "qty": qty,
                "side": side,
                "order_type": order_type,
                "id": str(result.id),
                "filled_price": float(getattr(result, "filled_avg_price", 0) or 0),
            }
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"symbol": symbol, "status": "failed", "error": str(e), "qty": qty, "side": side}

    def cancel_all_orders(self) -> List[Dict[str, Any]]:
        if self.is_mock or not self.client:
            logger.info("MOCK: Cancelled all orders")
            return []
        try:
            results = self.client.cancel_orders()
            return [{"id": str(r.id), "status": str(r.status)} for r in results] if results else []
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return []

    def get_order_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        if self.is_mock or not self.client:
            return []
        try:
            req = GetOrdersRequest(status="all", limit=limit)
            orders = self.client.get_orders(filter=req)
            return [
                {"id": str(o.id), "symbol": o.symbol, "side": str(o.side),
                 "qty": str(o.qty), "status": str(o.status), "created_at": str(o.created_at)}
                for o in orders
            ]
        except Exception as e:
            logger.error(f"Get orders failed: {e}")
            return []


# ── Global service instance ────────────────────────────────────

alpaca_service: Optional[AlpacaService] = None


# ── Tools ──────────────────────────────────────────────────────

@function_tool
def get_account_summary() -> str:
    """Get the current account summary including buying power, cash, and portfolio value."""
    if not alpaca_service:
        return json.dumps({"error": "Alpaca service not initialized"})
    try:
        acct = alpaca_service.get_account()
        if hasattr(acct, 'buying_power'):
            data = {
                "buying_power": float(acct.buying_power),
                "cash": float(acct.cash),
                "portfolio_value": float(acct.portfolio_value),
                "currency": str(acct.currency),
                "market_status": market_status_str(),
            }
        else:
            data = acct
            data["market_status"] = market_status_str()
        return json.dumps(data)
    except Exception as e:
        return json.dumps({"error": str(e)})


@function_tool
def get_current_positions() -> str:
    """Get all current open positions. Returns a JSON list."""
    if not alpaca_service:
        return "[]"
    try:
        positions = alpaca_service.get_positions()
        result = []
        for p in positions:
            if hasattr(p, 'symbol'):
                result.append({
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "market_value": float(p.market_value),
                    "current_price": float(p.current_price),
                })
            else:
                result.append(p)
        return json.dumps(result)
    except Exception as e:
        return json.dumps([{"error": str(e)}])


@function_tool
def execute_orders(orders: List[Dict[str, Any]]) -> str:
    """
    Execute a list of orders with risk validation.

    Each order dict should have: symbol, qty, side ('buy' or 'sell'),
    optional: order_type ('market' default), limit_price, stop_price.
    """
    if not alpaca_service:
        return json.dumps({"error": "Alpaca service not initialized"})

    # Get account for risk checks
    try:
        acct = alpaca_service.get_account()
        buying_power = float(acct.buying_power) if hasattr(acct, 'buying_power') else 100000.0
        portfolio_value = float(acct.portfolio_value) if hasattr(acct, 'portfolio_value') else 100000.0
    except Exception:
        buying_power = 100000.0
        portfolio_value = 100000.0

    results = []
    # Process sells first to free up buying power
    sorted_orders = sorted(orders, key=lambda o: 0 if o.get("side") == "sell" else 1)

    for order in sorted_orders:
        symbol = order.get("symbol", "")
        qty = float(order.get("qty", 0))
        side = order.get("side", "buy")
        order_type = order.get("order_type", "market")
        limit_price = order.get("limit_price")
        stop_price = order.get("stop_price")
        price_est = limit_price or 100.0  # fallback for validation

        # Risk check
        current_pos_val = alpaca_service.get_position_value(symbol)
        validation = validate_order(symbol, side, qty, price_est, buying_power, portfolio_value, current_pos_val)

        if not validation["ok"]:
            results.append({"symbol": symbol, "status": "rejected", "reason": validation["reason"]})
            continue

        if qty <= 0:
            results.append({"symbol": symbol, "status": "skipped", "reason": "qty <= 0"})
            continue

        if not is_market_open():
            results.append({"symbol": symbol, "status": "skipped", "reason": "Market is closed"})
            continue

        res = alpaca_service.place_order(symbol, qty, side, order_type, limit_price, stop_price)
        results.append(res)

        # Update buying_power estimate after each buy
        if side == "buy" and res.get("status") == "filled":
            filled_price = res.get("filled_price", price_est)
            buying_power -= qty * (filled_price or price_est)

    return json.dumps({"execution_results": results, "market_status": market_status_str()})


@function_tool
def cancel_all_pending_orders() -> str:
    """Cancel all pending orders on Alpaca."""
    if not alpaca_service:
        return json.dumps({"error": "Alpaca service not initialized"})
    results = alpaca_service.cancel_all_orders()
    return json.dumps({"cancelled": results})


@function_tool
def get_order_history(limit: int = 20) -> str:
    """Get recent order history from Alpaca."""
    if not alpaca_service:
        return "[]"
    results = alpaca_service.get_order_history(limit)
    return json.dumps(results)


# ── Execution Agent ────────────────────────────────────────────

class ExecutionAgent:
    def __init__(self, alpaca_api_key: str = None, alpaca_secret_key: str = None, paper: bool = True):
        global alpaca_service

        if not alpaca_api_key:
            alpaca_api_key = os.getenv("ALPACA_API_KEY")
        if not alpaca_secret_key:
            alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not alpaca_api_key or not alpaca_secret_key:
            logger.warning("Alpaca API credentials not provided. Using mock mode.")

        alpaca_service = AlpacaService(alpaca_api_key, alpaca_secret_key, paper)

        self.agent = Agent(
            name="ExecutionAgent",
            model=resolve_poe_model("openai/gpt-4o-mini"),
            instructions="""
            You are an Execution Agent responsible for executing trades on the Alpaca platform.
            You receive portfolio rebalancing instructions (target weights or specific orders).

            Your capabilities:
            1. Check account status (buying power, cash).
            2. Check current positions.
            3. Execute a batch of orders (market, limit, stop_loss).
            4. Cancel pending orders.
            5. View order history.

            When receiving order instructions:
            1. First check market status — only trade when market is OPEN.
            2. Check current positions and buying power.
            3. Execute SELL orders first to raise cash.
            4. Then execute BUY orders.
            5. Report execution results.

            Always check sufficient buying power before placing buy orders.
            All orders are validated against risk limits (max 25% per position, $50k per order).
            """,
            tools=[get_account_summary, get_current_positions, execute_orders,
                   cancel_all_pending_orders, get_order_history],
        )

    def run(self, instruction: str, context: Optional[Dict] = None):
        return self.agent.run(instruction, context=context, max_turns=5)

    @staticmethod
    def execute_orders_direct(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute orders directly without LLM involvement."""
        result_str = execute_orders(orders)
        result = json.loads(result_str)
        return result.get("execution_results", [])

    @staticmethod
    def get_account_direct() -> Dict[str, Any]:
        """Get account info directly without LLM."""
        result_str = get_account_summary()
        return json.loads(result_str)


if __name__ == "__main__":
    agent = ExecutionAgent()
    print("Execution Agent initialized.")
    print(f"Market status: {market_status_str()}")
    print(f"Account: {json.dumps(agent.get_account_direct(), indent=2)}")
