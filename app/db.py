import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models import SignalCandidate


KST = timezone(timedelta(hours=9))


def _connect(sqlite_path: str) -> sqlite3.Connection:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(sqlite_path: str) -> None:
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                score INTEGER NOT NULL,
                price REAL NOT NULL,
                change_pct REAL NOT NULL,
                reasons TEXT NOT NULL,
                risks TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                alerted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scan_rejection_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                markets TEXT NOT NULL,
                total_count INTEGER NOT NULL,
                passed_count INTEGER NOT NULL,
                rejected_count INTEGER NOT NULL,
                risk_counts_json TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scan_rejection_reports_created
            ON scan_rejection_reports (created_at)
            """
        )
        conn.commit()


def save_signal(sqlite_path: str, candidate: SignalCandidate, alerted: bool) -> None:
    snap = candidate.snapshot
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO signals (
                created_at, market, symbol, name, score, price, change_pct,
                reasons, risks, raw_json, alerted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(KST).isoformat(timespec="seconds"),
                snap.market,
                snap.symbol,
                snap.name,
                candidate.score,
                snap.price,
                snap.change_pct,
                json.dumps(candidate.reasons, ensure_ascii=False),
                json.dumps(candidate.risks, ensure_ascii=False),
                json.dumps(candidate.to_dict(), ensure_ascii=False),
                1 if alerted else 0,
            ),
        )
        conn.commit()


def get_latest_signals(sqlite_path: str, limit: int = 20) -> list[dict]:
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def was_recently_alerted(sqlite_path: str, symbol: str, cooldown_minutes: int) -> bool:
    threshold = datetime.now(KST) - timedelta(minutes=cooldown_minutes)
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT created_at FROM signals
            WHERE symbol = ? AND alerted = 1
            ORDER BY id DESC LIMIT 1
            """,
            (symbol,),
        ).fetchone()
    if not row:
        return False
    try:
        return datetime.fromisoformat(row["created_at"]) >= threshold
    except ValueError:
        return False


def save_scan_rejection_report(sqlite_path: str, markets: str, report: dict) -> None:
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO scan_rejection_reports (
                created_at, markets, total_count, passed_count, rejected_count,
                risk_counts_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(KST).isoformat(timespec="seconds"),
                markets,
                int(report.get("total") or 0),
                int(report.get("passed_count") or 0),
                int(report.get("rejected_count") or 0),
                json.dumps(report.get("risk_counts") or {}, ensure_ascii=False),
                json.dumps(report, ensure_ascii=False),
            ),
        )
        conn.commit()


def get_scan_rejection_summary(sqlite_path: str, days: int = 1) -> dict:
    threshold = datetime.now(KST) - timedelta(days=max(days, 1))
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM scan_rejection_reports
            WHERE created_at >= ?
            ORDER BY created_at ASC
            """,
            (threshold.isoformat(timespec="seconds"),),
        ).fetchall()

    risk_counts: Counter[str] = Counter()
    total_count = 0
    passed_count = 0
    rejected_count = 0
    for row in rows:
        total_count += int(row["total_count"])
        passed_count += int(row["passed_count"])
        rejected_count += int(row["rejected_count"])
        risk_counts.update(_load_json_dict(row["risk_counts_json"]))

    return {
        "days": max(days, 1),
        "scan_count": len(rows),
        "total_count": total_count,
        "passed_count": passed_count,
        "rejected_count": rejected_count,
        "pass_rate_pct": (passed_count / total_count) * 100 if total_count else 0,
        "risk_counts": dict(risk_counts.most_common()),
    }


def _load_json_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}
