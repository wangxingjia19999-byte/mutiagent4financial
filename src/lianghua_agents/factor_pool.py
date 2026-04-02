from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path


@dataclass
class FactorRecord:
    name: str
    expression: str
    description: str
    metrics: dict[str, float]
    ts_code: str
    source_agent: str = "factor_backtest"
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def score(self) -> float:
        ic_abs = abs(float(self.metrics.get("ic", 0.0)))
        sharpe = max(0.0, float(self.metrics.get("sharpe", 0.0)))
        win_rate = max(0.0, float(self.metrics.get("win_rate", 0.0)))
        annual_return = max(0.0, float(self.metrics.get("annual_return", 0.0)))
        return ic_abs * 45 + sharpe * 20 + win_rate * 20 + annual_return * 15


class FactorPool:
    def __init__(self, pool_path: str = ".factor_pool.json"):
        self.pool_path = Path(pool_path)
        self.records: list[FactorRecord] = []
        self.load()

    def load(self) -> None:
        if not self.pool_path.exists():
            self.records = []
            return

        try:
            raw = json.loads(self.pool_path.read_text(encoding="utf-8"))
            items = raw.get("factors", []) if isinstance(raw, dict) else []
            self.records = [FactorRecord(**item) for item in items if isinstance(item, dict)]
        except Exception:
            self.records = []

    def save(self) -> None:
        payload = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(self.records),
            "factors": [asdict(item) for item in self.records],
        }
        self.pool_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, record: FactorRecord) -> None:
        for idx, old in enumerate(self.records):
            if old.name == record.name and old.ts_code == record.ts_code:
                if record.score() >= old.score():
                    self.records[idx] = record
                return
        self.records.append(record)

    def add_effective(
        self,
        ts_code: str,
        factor_results: list[dict],
        min_ic_abs: float = 0.03,
        min_sharpe: float = 0.3,
        min_win_rate: float = 0.5,
    ) -> list[FactorRecord]:
        selected: list[FactorRecord] = []

        for item in factor_results:
            metrics = item.get("metrics", {})
            ic_abs = abs(float(metrics.get("ic", 0.0)))
            sharpe = float(metrics.get("sharpe", 0.0))
            win_rate = float(metrics.get("win_rate", 0.0))

            if ic_abs < min_ic_abs or sharpe < min_sharpe or win_rate < min_win_rate:
                continue

            record = FactorRecord(
                name=str(item.get("name", "unknown_factor")),
                expression=str(item.get("expression", "")),
                description=str(item.get("description", "")),
                metrics={
                    "ic": float(metrics.get("ic", 0.0)),
                    "sharpe": float(metrics.get("sharpe", 0.0)),
                    "annual_return": float(metrics.get("annual_return", 0.0)),
                    "win_rate": float(metrics.get("win_rate", 0.0)),
                    "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
                },
                ts_code=ts_code,
            )
            self.upsert(record)
            selected.append(record)

        if selected:
            self.records.sort(key=lambda x: x.score(), reverse=True)
            self.save()

        return selected

    def top(self, n: int = 10) -> list[FactorRecord]:
        return sorted(self.records, key=lambda x: x.score(), reverse=True)[:n]

    def summary(self, top_n: int = 8) -> str:
        if not self.records:
            return "因子池为空，尚无通过回测阈值的有效因子。"

        lines = [f"因子池规模: {len(self.records)}", "Top 因子:"]
        for idx, item in enumerate(self.top(top_n), start=1):
            metrics = item.metrics
            lines.append(
                f"{idx}. {item.name} ({item.ts_code}) | "
                f"IC={metrics.get('ic', 0.0):.4f}, "
                f"Sharpe={metrics.get('sharpe', 0.0):.2f}, "
                f"年化={metrics.get('annual_return', 0.0):.2%}, "
                f"胜率={metrics.get('win_rate', 0.0):.2%}"
            )
        return "\n".join(lines)
