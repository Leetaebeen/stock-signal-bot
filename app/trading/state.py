import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.trading.strategy import KST, Position


class JsonPositionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Position]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        positions = payload.get("positions") or []
        return {item["symbol"]: _position_from_json(item) for item in positions}

    def save(self, positions: dict[str, Position]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"positions": [_position_to_json(position) for position in positions.values()]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def upsert(self, position: Position) -> None:
        positions = self.load()
        positions[position.symbol] = position
        self.save(positions)

    def remove(self, symbol: str) -> Position | None:
        positions = self.load()
        removed = positions.pop(symbol, None)
        self.save(positions)
        return removed


def _position_to_json(position: Position) -> dict[str, object]:
    payload = asdict(position)
    payload["entry_at"] = position.entry_at.astimezone(KST).isoformat()
    return payload


def _position_from_json(payload: dict[str, object]) -> Position:
    entry_at = datetime.fromisoformat(str(payload["entry_at"]))
    return Position(
        symbol=str(payload["symbol"]),
        name=str(payload["name"]),
        market=str(payload["market"]),
        quantity=float(payload["quantity"]),
        entry_price=float(payload["entry_price"]),
        entry_at=entry_at,
        highest_price=float(payload["highest_price"]),
    )
