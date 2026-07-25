import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.trading.strategy import KST


@dataclass(frozen=True)
class FillRecord:
    order_no: str
    symbol: str
    name: str
    market: str
    side: str
    quantity: float
    price: float
    currency: str
    reason: str
    filled_at: datetime
    entry_price: float | None = None

    @property
    def pnl(self) -> float | None:
        if self.side.upper() != "SELL" or not self.entry_price:
            return None
        return (self.price - self.entry_price) * self.quantity

    @property
    def pnl_pct(self) -> float | None:
        if self.side.upper() != "SELL" or not self.entry_price:
            return None
        return ((self.price - self.entry_price) / self.entry_price) * 100


class TradeJournal:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record_fill(self, fill: FillRecord) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO trade_fills (
                    order_no, symbol, name, market, side, quantity, price,
                    entry_price, pnl, pnl_pct, currency, reason, filled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fill.order_no,
                    fill.symbol,
                    fill.name,
                    fill.market.upper(),
                    fill.side.upper(),
                    fill.quantity,
                    fill.price,
                    fill.entry_price,
                    fill.pnl,
                    fill.pnl_pct,
                    fill.currency.upper(),
                    fill.reason,
                    fill.filled_at.astimezone(KST).isoformat(),
                ),
            )
        return cursor.rowcount == 1

    def performance_summary(self) -> dict[str, dict[str, float | int]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    currency,
                    COUNT(*) AS trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) AS wins,
                    COALESCE(SUM(pnl), 0) AS realized_pnl,
                    COALESCE(AVG(pnl_pct), 0) AS average_pnl_pct
                FROM trade_fills
                WHERE side = 'SELL'
                GROUP BY currency
                """
            ).fetchall()
        return {
            str(row["currency"]): {
                "trades": int(row["trades"]),
                "wins": int(row["wins"]),
                "realized_pnl": float(row["realized_pnl"]),
                "average_pnl_pct": float(row["average_pnl_pct"]),
            }
            for row in rows
        }

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trade_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    entry_price REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    currency TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    filled_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_trade_fills_symbol_time ON trade_fills(symbol, filled_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection
