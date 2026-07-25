import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

from app.trading.strategy import KST, Position


@dataclass(frozen=True)
class PendingOrder:
    order_no: str
    market: str
    side: str
    symbol: str
    name: str
    quantity: float
    requested_price: float
    submitted_at: datetime
    reason: str
    exchange: str | None = None
    session: str = "regular"
    order_org_no: str | None = None
    cancel_requested_at: datetime | None = None
    cancel_attempts: int = 0


class JsonPositionStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Position]:
        payload = self._read()
        positions = payload.get("positions") or []
        return {item["symbol"]: _position_from_json(item) for item in positions}

    def save(self, positions: dict[str, Position]) -> None:
        payload = self._read()
        payload["positions"] = [_position_to_json(position) for position in positions.values()]
        payload.setdefault("pending_orders", [])
        self._write(payload)

    def upsert(self, position: Position) -> None:
        positions = self.load()
        positions[position.symbol] = position
        self.save(positions)

    def remove(self, symbol: str) -> Position | None:
        positions = self.load()
        removed = positions.pop(symbol, None)
        self.save(positions)
        return removed

    def load_pending_orders(self) -> list[PendingOrder]:
        payload = self._read()
        return [_pending_order_from_json(item) for item in payload.get("pending_orders") or []]

    def save_pending_orders(self, orders: list[PendingOrder]) -> None:
        payload = self._read()
        payload.setdefault("positions", [])
        payload["pending_orders"] = [_pending_order_to_json(order) for order in orders]
        self._write(payload)

    def save_state(
        self,
        positions: dict[str, Position],
        pending_orders: list[PendingOrder],
    ) -> None:
        self._write(
            {
                "positions": [_position_to_json(position) for position in positions.values()],
                "pending_orders": [_pending_order_to_json(order) for order in pending_orders],
            }
        )

    def add_pending_order(self, order: PendingOrder) -> None:
        orders = [item for item in self.load_pending_orders() if item.order_no != order.order_no]
        orders.append(order)
        self.save_pending_orders(orders)

    def remove_pending_order(self, order_no: str) -> PendingOrder | None:
        orders = self.load_pending_orders()
        removed = next((item for item in orders if item.order_no == order_no), None)
        self.save_pending_orders([item for item in orders if item.order_no != order_no])
        return removed

    def pending_for_symbol(self, symbol: str) -> PendingOrder | None:
        normalized = symbol.strip().upper()
        return next(
            (item for item in self.load_pending_orders() if item.symbol.strip().upper() == normalized),
            None,
        )

    def request_liquidation(self, symbol: str, market: str) -> Position:
        normalized_symbol = symbol.strip().upper()
        normalized_market = market.strip().upper()
        if self.pending_for_symbol(normalized_symbol):
            raise RuntimeError(f"{normalized_symbol} has a pending order.")

        positions = self.load()
        position = positions.get(normalized_symbol)
        if position is None:
            raise ValueError(f"Position not found: {normalized_symbol}")
        if position.market.strip().upper() != normalized_market:
            raise ValueError(
                f"Position market mismatch: expected {position.market}, got {normalized_market}"
            )

        requested = replace(position, managed=True, liquidation_requested=True)
        positions[normalized_symbol] = requested
        self.save(positions)
        return requested

    def _read(self) -> dict[str, object]:
        if not self.path.exists():
            return {"positions": [], "pending_orders": []}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid trading state file: {self.path}")
        return payload

    def _write(self, payload: dict[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary_path.replace(self.path)


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
        exchange=str(payload["exchange"]) if payload.get("exchange") else None,
        managed=bool(payload.get("managed", True)),
        liquidation_requested=bool(payload.get("liquidation_requested", False)),
    )


def _pending_order_to_json(order: PendingOrder) -> dict[str, object]:
    payload = asdict(order)
    payload["submitted_at"] = order.submitted_at.astimezone(KST).isoformat()
    payload["cancel_requested_at"] = (
        order.cancel_requested_at.astimezone(KST).isoformat()
        if order.cancel_requested_at
        else None
    )
    return payload


def _pending_order_from_json(payload: dict[str, object]) -> PendingOrder:
    return PendingOrder(
        order_no=str(payload["order_no"]),
        market=str(payload["market"]),
        side=str(payload["side"]),
        symbol=str(payload["symbol"]),
        name=str(payload["name"]),
        quantity=float(payload["quantity"]),
        requested_price=float(payload["requested_price"]),
        submitted_at=datetime.fromisoformat(str(payload["submitted_at"])),
        reason=str(payload.get("reason") or ""),
        exchange=str(payload["exchange"]) if payload.get("exchange") else None,
        session=str(payload.get("session") or "regular"),
        order_org_no=str(payload["order_org_no"]) if payload.get("order_org_no") else None,
        cancel_requested_at=(
            datetime.fromisoformat(str(payload["cancel_requested_at"]))
            if payload.get("cancel_requested_at")
            else None
        ),
        cancel_attempts=int(payload.get("cancel_attempts") or 0),
    )
