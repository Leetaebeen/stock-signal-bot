import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
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


@dataclass(frozen=True)
class RiskSnapshot:
    market: str
    lookback_hours: int
    buy_fills: int
    realized_pnl: float
    last_symbol_sell_at: datetime | None


@dataclass(frozen=True)
class SignalRecord:
    symbol: str
    name: str
    market: str
    exchange: str | None
    observed_at: datetime
    price: float
    change_pct: float
    volume_ratio: float
    trading_value_krw: float
    one_minute_change_pct: float
    five_minute_change_pct: float
    breakout_pct: float
    vwap_extension_pct: float
    confirmation_bars: int
    score: float
    source: str
    strategy_action: str
    strategy_reason: str
    execution_action: str
    execution_reason: str

    @property
    def observation_key(self) -> str:
        timestamp = self.observed_at.astimezone(KST).strftime("%Y%m%d%H%M%S")
        return f"{self.market.upper()}:{self.symbol.upper()}:{timestamp}"


@dataclass(frozen=True)
class SignalLabelTask:
    observation_id: int
    symbol: str
    market: str
    exchange: str | None
    entry_price: float
    horizon_minutes: int


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

    def risk_snapshot(
        self,
        *,
        market: str,
        symbol: str,
        now: datetime,
        lookback_hours: int = 24,
    ) -> RiskSnapshot:
        normalized_market = market.strip().upper()
        normalized_symbol = symbol.strip().upper()
        hours = max(int(lookback_hours), 1)
        since = now.astimezone(KST) - timedelta(hours=hours)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN side = 'BUY' THEN 1 ELSE 0 END) AS buy_fills,
                    COALESCE(SUM(CASE WHEN side = 'SELL' THEN pnl ELSE 0 END), 0) AS realized_pnl,
                    MAX(
                        CASE
                            WHEN side = 'SELL' AND symbol = ? THEN filled_at
                            ELSE NULL
                        END
                    ) AS last_symbol_sell_at
                FROM trade_fills
                WHERE market = ? AND filled_at >= ?
                """,
                (normalized_symbol, normalized_market, since.isoformat()),
            ).fetchone()
        last_sell = (
            datetime.fromisoformat(str(row["last_symbol_sell_at"]))
            if row and row["last_symbol_sell_at"]
            else None
        )
        return RiskSnapshot(
            market=normalized_market,
            lookback_hours=hours,
            buy_fills=int(row["buy_fills"] or 0) if row else 0,
            realized_pnl=float(row["realized_pnl"] or 0) if row else 0.0,
            last_symbol_sell_at=last_sell,
        )

    def record_signal(self, signal: SignalRecord) -> int:
        observed_at = signal.observed_at.astimezone(KST)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO signal_observations (
                    observation_key, symbol, name, market, exchange,
                    observed_at, observed_epoch, price, change_pct, volume_ratio,
                    trading_value_krw, one_minute_change_pct, five_minute_change_pct,
                    breakout_pct, vwap_extension_pct, confirmation_bars, score,
                    source, strategy_action, strategy_reason,
                    execution_action, execution_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.observation_key,
                    signal.symbol.upper(),
                    signal.name,
                    signal.market.upper(),
                    signal.exchange,
                    observed_at.isoformat(),
                    int(observed_at.timestamp()),
                    signal.price,
                    signal.change_pct,
                    signal.volume_ratio,
                    signal.trading_value_krw,
                    signal.one_minute_change_pct,
                    signal.five_minute_change_pct,
                    signal.breakout_pct,
                    signal.vwap_extension_pct,
                    signal.confirmation_bars,
                    signal.score,
                    signal.source,
                    signal.strategy_action.upper(),
                    signal.strategy_reason,
                    signal.execution_action.upper(),
                    signal.execution_reason,
                ),
            )
            row = connection.execute(
                "SELECT id FROM signal_observations WHERE observation_key = ?",
                (signal.observation_key,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Signal observation was not stored.")
        return int(row["id"])

    def due_signal_labels(
        self,
        now: datetime,
        *,
        tolerance_seconds: int = 180,
        limit: int = 20,
    ) -> list[SignalLabelTask]:
        now_epoch = int(now.astimezone(KST).timestamp())
        tasks: list[SignalLabelTask] = []
        with self._connect() as connection:
            for horizon in (5, 15, 30):
                if len(tasks) >= max(limit, 1):
                    break
                column = f"return_{horizon}m"
                target_offset = horizon * 60
                rows = connection.execute(
                    f"""
                    SELECT id, symbol, market, exchange, price
                    FROM signal_observations
                    WHERE {column} IS NULL
                      AND observed_epoch + ? <= ?
                      AND observed_epoch + ? >= ?
                    ORDER BY observed_epoch
                    LIMIT ?
                    """,
                    (
                        target_offset,
                        now_epoch,
                        target_offset + max(tolerance_seconds, 0),
                        now_epoch,
                        max(limit, 1) - len(tasks),
                    ),
                ).fetchall()
                tasks.extend(
                    SignalLabelTask(
                        observation_id=int(row["id"]),
                        symbol=str(row["symbol"]),
                        market=str(row["market"]),
                        exchange=str(row["exchange"]) if row["exchange"] else None,
                        entry_price=float(row["price"]),
                        horizon_minutes=horizon,
                    )
                    for row in rows
                )
        return tasks

    def update_signal_label(
        self,
        task: SignalLabelTask,
        *,
        current_price: float,
        labeled_at: datetime,
    ) -> bool:
        if task.horizon_minutes not in {5, 15, 30}:
            raise ValueError("horizon_minutes must be 5, 15, or 30.")
        if task.entry_price <= 0 or current_price <= 0:
            return False
        return_pct = ((current_price - task.entry_price) / task.entry_price) * 100
        return_column = f"return_{task.horizon_minutes}m"
        time_column = f"labeled_{task.horizon_minutes}m_at"
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE signal_observations
                SET {return_column} = ?, {time_column} = ?
                WHERE id = ? AND {return_column} IS NULL
                """,
                (
                    return_pct,
                    labeled_at.astimezone(KST).isoformat(),
                    task.observation_id,
                ),
            )
        return cursor.rowcount == 1

    def signal_summary(self) -> dict[str, float | int]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS observations,
                    COUNT(return_5m) AS labeled_5m,
                    COUNT(return_15m) AS labeled_15m,
                    COUNT(return_30m) AS labeled_30m,
                    COALESCE(AVG(return_5m), 0) AS average_return_5m,
                    COALESCE(AVG(return_15m), 0) AS average_return_15m,
                    COALESCE(AVG(return_30m), 0) AS average_return_30m
                FROM signal_observations
                """
            ).fetchone()
        if row is None:
            return {}
        return {
            "observations": int(row["observations"]),
            "labeled_5m": int(row["labeled_5m"]),
            "labeled_15m": int(row["labeled_15m"]),
            "labeled_30m": int(row["labeled_30m"]),
            "average_return_5m": float(row["average_return_5m"]),
            "average_return_15m": float(row["average_return_15m"]),
            "average_return_30m": float(row["average_return_30m"]),
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS signal_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observation_key TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    market TEXT NOT NULL,
                    exchange TEXT,
                    observed_at TEXT NOT NULL,
                    observed_epoch INTEGER NOT NULL,
                    price REAL NOT NULL,
                    change_pct REAL NOT NULL,
                    volume_ratio REAL NOT NULL,
                    trading_value_krw REAL NOT NULL,
                    one_minute_change_pct REAL NOT NULL,
                    five_minute_change_pct REAL NOT NULL,
                    breakout_pct REAL NOT NULL,
                    vwap_extension_pct REAL NOT NULL,
                    confirmation_bars INTEGER NOT NULL,
                    score REAL NOT NULL,
                    source TEXT NOT NULL,
                    strategy_action TEXT NOT NULL,
                    strategy_reason TEXT NOT NULL,
                    execution_action TEXT NOT NULL,
                    execution_reason TEXT NOT NULL,
                    return_5m REAL,
                    return_15m REAL,
                    return_30m REAL,
                    labeled_5m_at TEXT,
                    labeled_15m_at TEXT,
                    labeled_30m_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_signal_observations_due
                ON signal_observations(observed_epoch, market)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection
