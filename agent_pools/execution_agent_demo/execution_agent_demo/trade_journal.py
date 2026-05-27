"""
Trade Journal — records every trading decision and execution result,
just like a real trader would keep a trading log.
"""

import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("TradeJournal")

JOURNAL_DIR = Path(__file__).resolve().parents[3] / "trade_journals"


class TradeJournal:
    def __init__(self, journal_dir: Optional[Path] = None):
        self.dir = journal_dir or JOURNAL_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self._current_cycle: Dict[str, Any] = {}
        self._cycle_id = 0

    # ── per-cycle logging ──────────────────────────────────────

    def start_cycle(self, cycle_id: int, market_status: str = "UNKNOWN") -> None:
        self._cycle_id = cycle_id
        self._current_cycle = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle_id": cycle_id,
            "market_status": market_status,
            "signals": {},
            "risk_level": "UNKNOWN",
            "decisions": [],
            "executions": [],
        }

    def log_signals(self, signals: Dict[str, float], risk_level: str) -> None:
        self._current_cycle["signals"] = signals
        self._current_cycle["risk_level"] = risk_level

    def log_decisions(self, decisions: List[Dict[str, Any]]) -> None:
        self._current_cycle["decisions"] = decisions

    def log_execution(self, order: Dict[str, Any], result: Dict[str, Any]) -> None:
        entry = {
            "symbol": order.get("symbol", "?"),
            "side": order.get("side", "?"),
            "qty": order.get("qty", 0),
            "order_type": order.get("order_type", "market"),
            "status": result.get("status", "unknown"),
            "filled_price": result.get("filled_price"),
            "error": result.get("error"),
        }
        self._current_cycle["executions"].append(entry)

    def finish_cycle(self) -> None:
        if not self._current_cycle:
            return
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = self.dir / f"{today}.jsonl"
        with open(filepath, "a") as f:
            f.write(json.dumps(self._current_cycle, ensure_ascii=False) + "\n")
        logger.info("Cycle %d journal written to %s", self._cycle_id, filepath)

    # ── daily summary ──────────────────────────────────────────

    def log_daily_summary(self, pnl: float, pnl_pct: float, positions: List[Dict[str, Any]]) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filepath = self.dir / f"{today}_summary.json"
        summary = {
            "date": today,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 4),
            "positions": positions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(filepath, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info("Daily summary written to %s", filepath)

    # ── read-back helpers ──────────────────────────────────────

    def load_cycles_for_date(self, date_str: str) -> List[Dict[str, Any]]:
        filepath = self.dir / f"{date_str}.jsonl"
        if not filepath.exists():
            return []
        cycles = []
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    cycles.append(json.loads(line))
        return cycles

    def load_latest_summary(self) -> Optional[Dict[str, Any]]:
        summaries = sorted(self.dir.glob("*_summary.json"), reverse=True)
        if not summaries:
            return None
        with open(summaries[0]) as f:
            return json.load(f)
