"""
Alpaca Broker — implements Broker interface for US stocks via Alpaca Trading API.

Wraps the existing AlpacaService logic from execution_agent.py.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from .base import Broker, AccountInfo, Position, OrderResult
from market import US_MARKET, MarketConfig

logger = logging.getLogger("AlpacaBroker")

# Risk control defaults (US market)
MAX_POSITION_PCT = 0.05    # max 5% of portfolio in a single stock
MAX_ORDER_VALUE = 200_000.0
MIN_ORDER_VALUE = 50.0


class AlpacaBroker(Broker):
    """US stock broker via Alpaca Trading API."""

    def __init__(
        self,
        api_key: str = None,
        secret_key: str = None,
        paper: bool = True,
        config: MarketConfig = US_MARKET,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.paper = paper
        self.config = config
        self._client = None
        self._is_mock = False

        if not self.api_key or "MOCK" in self.api_key.upper():
            self._is_mock = True
            logger.info("Using Mock Alpaca Broker (invalid or mock keys)")
            return

        try:
            from alpaca.trading.client import TradingClient
            self._client = TradingClient(self.api_key, self.secret_key, paper=paper)
            logger.info("Connected to Alpaca %s Trading", "Paper" if paper else "Live")
        except ImportError:
            logger.warning("Alpaca SDK not available — using mock mode")
            self._is_mock = True
        except Exception as e:
            logger.error("Failed to connect to Alpaca: %s", e)
            self._is_mock = True

    @property
    def client(self):
        return self._client

    @property
    def is_mock(self) -> bool:
        return self._is_mock

    # ── Account ────────────────────────────────────────────────────

    def get_account(self) -> AccountInfo:
        if not self._is_mock and self._client:
            try:
                acct = self._client.get_account()
                return AccountInfo(
                    buying_power=float(acct.buying_power),
                    cash=float(acct.cash),
                    portfolio_value=float(acct.portfolio_value),
                    currency=str(acct.currency),
                    status=str(acct.status),
                )
            except Exception as e:
                logger.warning("Alpaca API error: %s. Falling back to mock.", e)

        return AccountInfo(
            buying_power=100_000.0,
            cash=50_000.0,
            portfolio_value=150_000.0,
            currency="USD",
            status="ACTIVE",
        )

    # ── Positions ─────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        if self._is_mock or not self._client:
            return []

        try:
            raw = self._client.get_all_positions()
            return [
                Position(
                    symbol=p.symbol,
                    qty=float(p.qty),
                    market_value=float(p.market_value),
                    current_price=float(p.current_price),
                    cost_basis=float(getattr(p, "cost_basis", 0) or 0),
                )
                for p in raw
            ]
        except Exception:
            return []

    # ── Order Placement ───────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "day",
    ) -> OrderResult:
        if self._is_mock or not self._client:
            logger.info("MOCK ORDER: %s %s %s (%s)", side, qty, symbol, order_type)
            return OrderResult(
                symbol=symbol,
                status="filled",
                qty=qty,
                side=side,
                filled_price=100.0,
                order_type=order_type,
                order_id=f"mock_{symbol}",
            )

        try:
            from alpaca.trading.requests import (
                MarketOrderRequest,
                LimitOrderRequest,
                StopOrderRequest,
            )
            from alpaca.trading.enums import OrderSide, TimeInForce, OrderType

            order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

            if order_type == "limit" and limit_price:
                req = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    limit_price=limit_price,
                    time_in_force=TimeInForce.DAY,
                )
            elif order_type == "stop_loss" and stop_price:
                req = StopOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    stop_price=stop_price,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                req = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                )

            result = self._client.submit_order(order_data=req)
            return OrderResult(
                symbol=symbol,
                status=str(result.status),
                qty=qty,
                side=side,
                order_type=order_type,
                order_id=str(result.id),
                filled_price=float(getattr(result, "filled_avg_price", 0) or 0),
            )
        except Exception as e:
            logger.error("Order failed: %s", e)
            return OrderResult(
                symbol=symbol,
                status="failed",
                qty=qty,
                side=side,
                error=str(e),
            )

    # ── Cancel / History ──────────────────────────────────────────

    def cancel_all_orders(self) -> List[Dict[str, Any]]:
        if self._is_mock or not self._client:
            logger.info("MOCK: Cancelled all orders")
            return []
        try:
            results = self._client.cancel_orders()
            return (
                [{"id": str(r.id), "status": str(r.status)} for r in results]
                if results
                else []
            )
        except Exception as e:
            logger.error("Cancel failed: %s", e)
            return []

    def get_order_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        if self._is_mock or not self._client:
            return []
        try:
            from alpaca.trading.requests import GetOrdersRequest

            req = GetOrdersRequest(status="all", limit=limit)
            orders = self._client.get_orders(filter=req)
            return [
                {
                    "id": str(o.id),
                    "symbol": o.symbol,
                    "side": str(o.side),
                    "qty": str(o.qty),
                    "status": str(o.status),
                    "created_at": str(o.created_at),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error("Get orders failed: %s", e)
            return []
