"""
CN Paper Broker — in-memory simulated broker for A-share paper trading.

Implements the Broker interface with A-share specific rules:
    - T+1 settlement: shares bought today cannot be sold today
    - Price limits: ±10% for main board, ±20% for ChiNext/STAR
    - Round lots: 100 shares per lot
    - FIFO cost basis tracking for realized P&L
"""

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from .base import Broker, AccountInfo, Position, OrderResult
from market import CN_MARKET, MarketConfig
from market.cn_calendar import CNMarketCalendar

logger = logging.getLogger("CNPaperBroker")


# ── Internal data structures ──────────────────────────────────────

@dataclass
class Lot:
    """A tax lot — shares bought on a specific date at a specific price."""
    qty: int           # number of shares
    buy_price: float   # purchase price per share
    buy_date: date     # purchase date (for T+1 tracking)


@dataclass
class PositionState:
    """Internal position tracking with lot-level granularity."""
    symbol: str
    lots: List[Lot] = field(default_factory=list)
    _prev_close: float = 0.0

    @property
    def total_qty(self) -> int:
        return sum(lot.qty for lot in self.lots)

    @property
    def cost_basis(self) -> float:
        if self.total_qty == 0:
            return 0.0
        return sum(lot.qty * lot.buy_price for lot in self.lots) / self.total_qty

    @property
    def sellable_qty(self) -> int:
        """Shares available for sale (T+1: exclude today's purchases)."""
        today = date.today()
        return sum(lot.qty for lot in self.lots if lot.buy_date < today)

    @property
    def locked_qty(self) -> int:
        """Shares locked by T+1 (bought today)."""
        today = date.today()
        return sum(lot.qty for lot in self.lots if lot.buy_date >= today)

    def add_lot(self, qty: int, price: float, buy_date: date):
        self.lots.append(Lot(qty=qty, buy_price=price, buy_date=buy_date))

    def sell(self, qty: int) -> float:
        """Remove qty from oldest lots first (FIFO). Returns realized cost basis."""
        remaining = qty
        cost_basis = 0.0
        new_lots = []
        for lot in self.lots:
            if remaining <= 0:
                new_lots.append(lot)
            elif lot.qty <= remaining:
                remaining -= lot.qty
                cost_basis += lot.qty * lot.buy_price
            else:
                lot.qty -= remaining
                cost_basis += remaining * lot.buy_price
                remaining = 0
                new_lots.append(lot)
        self.lots = new_lots
        return cost_basis / qty if qty > 0 else 0.0


# ── CNPaperBroker ─────────────────────────────────────────────────

class CNPaperBroker(Broker):
    """In-memory A-share paper trading broker.

    Maintains simulated portfolio with:
        - T+1 settlement enforcement
        - ±10% daily price limits (configurable per board)
        - 100-share round lot sizing
        - CNY-denominated account
    """

    # Price limit per board
    PRICE_LIMIT = {
        "main": 0.10,       # 主板 600/000
        "chimext": 0.20,    # 创业板 300
        "star": 0.20,       # 科创板 688
        "bse": 0.30,        # 北交所 8/4
    }

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        config: MarketConfig = CN_MARKET,
        data_provider=None,
    ):
        self.config = config
        self._data_provider = data_provider
        self._cash = initial_capital
        self._positions: Dict[str, PositionState] = {}
        self._prev_closes: Dict[str, float] = {}  # for price limit checking
        self._orders: List[OrderResult] = []
        self._order_id_counter = 0
        self._calendar = CNMarketCalendar()
        logger.info("CNPaperBroker initialized: capital=¥%.0f, lot=%d, limit=%.0f%%",
                     initial_capital, config.lot_size, (config.price_limit_pct or 0.10) * 100)

    # ── Account ────────────────────────────────────────────────────

    def get_account(self) -> AccountInfo:
        total_mv = sum(
            p.total_qty * self._get_price(p.symbol) for p in self._positions.values()
        )
        return AccountInfo(
            buying_power=self._cash,
            cash=self._cash,
            portfolio_value=self._cash + total_mv,
            currency=self.config.currency,
            status="ACTIVE",
        )

    # ── Positions ─────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        result = []
        for symbol, state in self._positions.items():
            if state.total_qty > 0:
                price = self._get_price(symbol)
                result.append(Position(
                    symbol=symbol,
                    qty=state.total_qty,
                    market_value=state.total_qty * price,
                    current_price=price,
                    cost_basis=state.cost_basis,
                ))
        return result

    def get_position_value(self, symbol: str) -> float:
        state = self._positions.get(symbol)
        if state and state.total_qty > 0:
            return state.total_qty * self._get_price(symbol)
        return 0.0

    # ── Price Helpers ──────────────────────────────────────────────

    def _get_price(self, symbol: str) -> float:
        """Get current price for a symbol (from provider or stored prev close)."""
        if self._data_provider:
            prices = self._data_provider.get_realtime_prices([symbol])
            if symbol in prices and prices[symbol] > 0:
                return prices[symbol]
        return self._prev_closes.get(symbol, 10.0)

    def _get_prev_close(self, symbol: str) -> float:
        """Get previous close. Returns 0.0 if unknown — price limit check is skipped."""
        return self._prev_closes.get(symbol, 0.0)

    def _get_board_limit(self, symbol: str) -> float:
        """Determine price limit based on stock code prefix."""
        code = symbol.split(".")[0] if "." in symbol else symbol
        if code.startswith("300"):
            return self.PRICE_LIMIT["chimext"]   # 创业板
        elif code.startswith("688"):
            return self.PRICE_LIMIT["star"]       # 科创板
        elif code.startswith("8") or code.startswith("4"):
            return self.PRICE_LIMIT["bse"]        # 北交所
        return self.PRICE_LIMIT["main"]           # 主板

    def _apply_price_limit(self, symbol: str, price: float) -> float:
        """Clamp price to daily limit range."""
        prev_close = self._get_prev_close(symbol)
        if prev_close <= 0:
            return price

        limit = self._get_board_limit(symbol)
        max_price = prev_close * (1 + limit)
        min_price = prev_close * (1 - limit)
        return max(min_price, min(price, max_price))

    def update_market_prices(self, prices: Dict[str, float]):
        """Update reference prices (call before trading, e.g., after fetching daily data)."""
        for symbol, price in prices.items():
            self._prev_closes[symbol] = price

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
        """Place an order with A-share rule validation."""
        lot_size = self.config.lot_size
        self._order_id_counter += 1
        order_id = f"cn_{self._order_id_counter:06d}"
        side_lower = side.lower().strip()

        # ── 1. Round to lot ──
        qty_int = (int(qty) // lot_size) * lot_size
        if qty_int < lot_size:
            return OrderResult(
                symbol=symbol, status="rejected", qty=0, side=side_lower,
                error=f"Order qty {qty_int} below minimum lot size of {lot_size}",
                order_id=order_id,
            )

        # ── 2. Get reference price ──
        price = limit_price if limit_price else self._get_price(symbol)
        prev_close = self._get_prev_close(symbol)

        # ── 3. Check price limit ──
        if prev_close > 0:
            limit = self._get_board_limit(symbol)
            max_price = prev_close * (1 + limit)
            min_price = prev_close * (1 - limit)
            if price > max_price:
                return OrderResult(
                    symbol=symbol, status="rejected", qty=qty_int, side=side_lower,
                    error=f"Price {price:.2f} exceeds upper limit {max_price:.2f} ({limit:.0%})",
                    order_id=order_id,
                )
            if price < min_price:
                return OrderResult(
                    symbol=symbol, status="rejected", qty=qty_int, side=side_lower,
                    error=f"Price {price:.2f} below lower limit {min_price:.2f} ({limit:.0%})",
                    order_id=order_id,
                )

        # ── 4. Market closed check ──
        if not self._calendar.is_open():
            # For paper mode, allow orders when market is closed but note it
            logger.info("Market is closed — paper order accepted (simulation mode)")

        # ── 5. Execute ──
        if side_lower == "buy":
            return self._execute_buy(symbol, qty_int, price, order_id)
        elif side_lower == "sell":
            return self._execute_sell(symbol, qty_int, price, order_id)
        else:
            return OrderResult(
                symbol=symbol, status="rejected", qty=qty_int, side=side_lower,
                error=f"Unknown side: {side}", order_id=order_id,
            )

    def _execute_buy(self, symbol: str, qty: int, price: float, order_id: str) -> OrderResult:
        cost = qty * price
        # Add stamp duty + commission (A-share: no stamp duty on buy,
        # but ~0.005% commission + 0.002% transfer fee)
        commission = max(self.config.min_commission, cost * 0.00025)
        total_cost = cost + commission

        if total_cost > self._cash:
            return OrderResult(
                symbol=symbol, status="rejected", qty=qty, side="buy",
                error=f"Insufficient cash: need ¥{total_cost:.0f}, have ¥{self._cash:.0f}",
                order_id=order_id,
            )

        self._cash -= total_cost

        if symbol not in self._positions:
            self._positions[symbol] = PositionState(symbol=symbol)

        self._positions[symbol].add_lot(qty, price, date.today())
        logger.info("BUY  %s x%d @ ¥%.2f = ¥%.0f (commission: ¥%.0f, cash: ¥%.0f)",
                     symbol, qty, price, cost, commission, self._cash)

        return OrderResult(
            symbol=symbol, status="filled", qty=qty, side="buy",
            filled_price=price, order_id=order_id,
        )

    def _execute_sell(self, symbol: str, qty: int, price: float, order_id: str) -> OrderResult:
        if symbol not in self._positions:
            return OrderResult(
                symbol=symbol, status="rejected", qty=qty, side="sell",
                error=f"No position in {symbol}", order_id=order_id,
            )

        state = self._positions[symbol]

        # T+1 check
        sellable = state.sellable_qty
        locked = state.locked_qty
        if sellable < qty:
            return OrderResult(
                symbol=symbol, status="rejected", qty=qty, side="sell",
                error=f"T+1 restriction: only {sellable} shares sellable ({locked} locked until tomorrow)",
                order_id=order_id,
            )

        # Execute (FIFO)
        cost_basis_price = state.sell(qty)
        proceeds = qty * price
        # A-share: 0.05% stamp duty on sell + commission + transfer fee
        stamp_duty = proceeds * self.config.stamp_duty_sell
        commission = max(self.config.min_commission, proceeds * 0.00025)
        total_fee = stamp_duty + commission
        net_proceeds = proceeds - total_fee

        self._cash += net_proceeds

        # Remove empty position
        if state.total_qty == 0:
            del self._positions[symbol]

        realized_pnl = net_proceeds - (qty * cost_basis_price)
        logger.info("SELL %s x%d @ ¥%.2f = ¥%.0f (fees: ¥%.0f, PnL: ¥%.0f, cash: ¥%.0f)",
                     symbol, qty, price, proceeds, total_fee, realized_pnl, self._cash)

        return OrderResult(
            symbol=symbol, status="filled", qty=qty, side="sell",
            filled_price=price, order_id=order_id,
        )

    # ── Cancel / History ──────────────────────────────────────────

    def cancel_all_orders(self) -> List[Dict[str, Any]]:
        # Paper broker executes immediately, so no pending orders to cancel
        return []

    def get_order_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        orders = self._orders[-limit:]
        return [
            {
                "id": o.order_id or "",
                "symbol": o.symbol,
                "side": o.side,
                "qty": str(o.qty),
                "status": o.status,
                "filled_price": o.filled_price or 0,
                "error": o.error or "",
                "timestamp": o.timestamp.isoformat() if o.timestamp else "",
            }
            for o in orders
        ]

    # ── Simulation Utilities ──────────────────────────────────────

    def reset(self, initial_capital: float = None):
        """Reset the paper broker to initial state."""
        if initial_capital is not None:
            self._cash = initial_capital
        self._positions.clear()
        self._prev_closes.clear()
        self._orders.clear()
        logger.info("CNPaperBroker reset: capital=¥%.0f", self._cash)

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Return a summary of current portfolio state."""
        acct = self.get_account()
        positions = self.get_positions()

        total_pnl = 0.0
        for pos in positions:
            if pos.cost_basis and pos.cost_basis > 0:
                total_pnl += pos.market_value - pos.qty * pos.cost_basis

        return {
            "cash": acct.cash,
            "portfolio_value": acct.portfolio_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl / (acct.portfolio_value - total_pnl)
                if (acct.portfolio_value - total_pnl) > 0 else 0,
            "positions": len(positions),
            "position_details": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "market_value": p.market_value,
                    "cost_basis": p.cost_basis,
                    "unrealized_pnl": p.market_value - (p.qty * p.cost_basis)
                        if p.cost_basis else 0,
                    "current_price": p.current_price,
                }
                for p in positions
            ],
        }
