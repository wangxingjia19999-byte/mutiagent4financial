from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any, Literal

try:
    from .stock_data import TushareClient
except ImportError:
    current_dir = Path(__file__).resolve().parent
    src_dir = current_dir.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from lianghua_agents.stock_data import TushareClient

Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Position:
    ts_code: str
    quantity: int = 0
    avg_price: float = 0.0
    last_price: float = 0.0


@dataclass
class TradeRecord:
    ts_code: str
    action: Signal
    quantity: int
    price: float
    amount: float
    commission: float
    timestamp: str
    reason: str = ""


@dataclass
class PaperAccount:
    cash: float = 1_000_000.0
    positions: dict[str, Position] = field(default_factory=dict)
    history: list[TradeRecord] = field(default_factory=list)


@dataclass
class ParsedDecision:
    signal: Signal
    score: int | None
    verdict: str


class PaperTradingEngine:
    def __init__(
        self,
        tushare_token: str | None = None,
        state_path: str = ".paper_account.json",
        initial_cash: float = 1_000_000.0,
    ):
        self.client = TushareClient(token=tushare_token)
        self.state_path = Path(state_path)
        self.initial_cash = float(initial_cash)
        self.account = self._load_account()

    @staticmethod
    def parse_investment_decision(text: str) -> ParsedDecision:
        verdict = ""
        score: int | None = None
        signal: Signal = "HOLD"

        verdict_match = re.search(r"综合结论\s*[:：]\s*([^\n]+)", text)
        if verdict_match:
            verdict = verdict_match.group(1).strip()

        score_match = re.search(r"综合评分\s*\(?\s*0\s*-\s*100\s*\)?\s*[:：]\s*(\d{1,3})", text)
        if score_match:
            score = max(0, min(100, int(score_match.group(1))))

        normalized = verdict or text
        if "可投资" in normalized and "暂不" not in normalized:
            signal = "BUY"
        elif "暂不投资" in normalized:
            signal = "SELL"
        elif "谨慎观察" in normalized:
            signal = "HOLD"

        return ParsedDecision(signal=signal, score=score, verdict=verdict)

    def _load_account(self) -> PaperAccount:
        if not self.state_path.exists():
            return PaperAccount(cash=self.initial_cash)

        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            positions = {
                k: Position(**v)
                for k, v in raw.get("positions", {}).items()
            }
            history = [TradeRecord(**item) for item in raw.get("history", [])]
            return PaperAccount(
                cash=float(raw.get("cash", self.initial_cash)),
                positions=positions,
                history=history,
            )
        except Exception:
            return PaperAccount(cash=self.initial_cash)

    def save(self) -> None:
        payload = {
            "cash": self.account.cash,
            "positions": {k: asdict(v) for k, v in self.account.positions.items()},
            "history": [asdict(item) for item in self.account.history[-1000:]],
        }
        self.state_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _latest_price(self, ts_code: str, start_date: str | None = None, end_date: str | None = None) -> float:
        daily = self.client.get_daily(ts_code=ts_code, start_date=start_date, end_date=end_date, limit=1)
        if daily.empty:
            raise ValueError(f"无法获取 {ts_code} 最新价格")
        return float(daily.iloc[0]["close"])

    @staticmethod
    def _calc_commission(amount: float) -> float:
        return max(5.0, amount * 0.0003)

    def _position_value(self, ts_code: str, last_price: float) -> float:
        position = self.account.positions.get(ts_code)
        if not position:
            return 0.0
        return float(position.quantity) * float(last_price)

    def account_nav(self, latest_prices: dict[str, float] | None = None) -> float:
        latest_prices = latest_prices or {}
        holdings = 0.0
        for code, position in self.account.positions.items():
            px = latest_prices.get(code, position.last_price or position.avg_price)
            holdings += px * position.quantity
        return self.account.cash + holdings

    def _target_position_ratio(self, risk_level: str | None) -> float:
        risk = (risk_level or "中等").strip()
        mapping = {
            "保守": 0.2,
            "中等": 0.35,
            "积极": 0.5,
        }
        return mapping.get(risk, 0.35)

    def _round_lot(self, quantity: int) -> int:
        if quantity <= 0:
            return 0
        return (quantity // 100) * 100

    def check_stop_loss(self, ts_code: str, last_price: float, stop_loss_pct: float = 0.08) -> TradeRecord | None:
        position = self.account.positions.get(ts_code)
        if not position or position.quantity <= 0 or position.avg_price <= 0:
            return None

        drawdown = (position.avg_price - last_price) / position.avg_price
        if drawdown < stop_loss_pct:
            return None

        quantity = position.quantity
        amount = quantity * last_price
        commission = self._calc_commission(amount)
        self.account.cash += amount - commission
        self.account.positions.pop(ts_code, None)

        record = TradeRecord(
            ts_code=ts_code,
            action="SELL",
            quantity=quantity,
            price=last_price,
            amount=amount,
            commission=commission,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            reason=f"触发止损: 回撤 {drawdown:.2%}",
        )
        self.account.history.append(record)
        return record

    def execute_signal(
        self,
        ts_code: str,
        signal: Signal,
        last_price: float,
        risk_level: str | None = None,
        reason: str = "",
    ) -> TradeRecord | None:
        position = self.account.positions.get(ts_code, Position(ts_code=ts_code))
        position.last_price = last_price

        if signal == "HOLD":
            self.account.positions[ts_code] = position
            return None

        if signal == "SELL":
            quantity = position.quantity
            if quantity <= 0:
                self.account.positions[ts_code] = position
                return None

            amount = quantity * last_price
            commission = self._calc_commission(amount)
            self.account.cash += amount - commission
            self.account.positions.pop(ts_code, None)

            record = TradeRecord(
                ts_code=ts_code,
                action="SELL",
                quantity=quantity,
                price=last_price,
                amount=amount,
                commission=commission,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                reason=reason,
            )
            self.account.history.append(record)
            return record

        ratio = self._target_position_ratio(risk_level)
        nav = self.account_nav({ts_code: last_price})
        target_value = nav * ratio
        current_value = self._position_value(ts_code, last_price)
        need_value = max(0.0, target_value - current_value)

        quantity = self._round_lot(int(need_value / last_price))
        if quantity <= 0:
            self.account.positions[ts_code] = position
            return None

        amount = quantity * last_price
        commission = self._calc_commission(amount)
        total_cost = amount + commission
        if total_cost > self.account.cash:
            affordable = self._round_lot(int(self.account.cash / (last_price * 1.001)))
            if affordable <= 0:
                self.account.positions[ts_code] = position
                return None
            quantity = affordable
            amount = quantity * last_price
            commission = self._calc_commission(amount)
            total_cost = amount + commission

        if total_cost > self.account.cash:
            self.account.positions[ts_code] = position
            return None

        new_qty = position.quantity + quantity
        if new_qty <= 0:
            self.account.positions[ts_code] = position
            return None

        weighted_cost = position.avg_price * position.quantity + amount
        position.quantity = new_qty
        position.avg_price = weighted_cost / new_qty
        position.last_price = last_price

        self.account.cash -= total_cost
        self.account.positions[ts_code] = position

        record = TradeRecord(
            ts_code=ts_code,
            action="BUY",
            quantity=quantity,
            price=last_price,
            amount=amount,
            commission=commission,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            reason=reason,
        )
        self.account.history.append(record)
        return record

    def run_once(
        self,
        ts_code: str,
        decision_text: str,
        start_date: str | None = None,
        end_date: str | None = None,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        last_price = self._latest_price(ts_code=ts_code, start_date=start_date, end_date=end_date)

        stop_record = self.check_stop_loss(ts_code=ts_code, last_price=last_price)

        parsed = self.parse_investment_decision(decision_text)
        reason = parsed.verdict or f"signal={parsed.signal}, score={parsed.score}"
        trade_record = self.execute_signal(
            ts_code=ts_code,
            signal=parsed.signal,
            last_price=last_price,
            risk_level=risk_level,
            reason=reason,
        )

        self.save()

        latest_prices = {ts_code: last_price}
        nav = self.account_nav(latest_prices=latest_prices)
        position = self.account.positions.get(ts_code)

        return {
            "ts_code": ts_code,
            "last_price": last_price,
            "decision": asdict(parsed),
            "stop_loss_trade": asdict(stop_record) if stop_record else None,
            "executed_trade": asdict(trade_record) if trade_record else None,
            "cash": round(self.account.cash, 2),
            "position": asdict(position) if position else None,
            "nav": round(nav, 2),
            "history_count": len(self.account.history),
            "state_path": str(self.state_path),
        }
