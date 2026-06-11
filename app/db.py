import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

from app.models import AIAnalysis, AIRecommendation, SignalCandidate, TradePlan

KST = timezone(timedelta(hours=9))
ACTIVE_SIGNAL_STATUSES = ("WATCHING", "UPTREND")


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
            CREATE TABLE IF NOT EXISTS signal_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL NOT NULL,
                target_price REAL NOT NULL,
                stop_price REAL NOT NULL,
                last_alert_price REAL NOT NULL,
                score INTEGER NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_signal_states_symbol_status
            ON signal_states (market, symbol, status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_analysis_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                score INTEGER NOT NULL,
                recommendation TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                summary TEXT NOT NULL,
                key_points TEXT NOT NULL,
                risk_notes TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_cache_symbol_created
            ON ai_analysis_cache (market, symbol, created_at)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                checked_at TEXT,
                market TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                horizon_minutes INTEGER NOT NULL,
                entry_price REAL NOT NULL,
                observed_price REAL,
                pnl_pct REAL,
                status TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                UNIQUE(state_id, horizon_minutes)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_signal_outcomes_due_status
            ON signal_outcomes (status, due_at)
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


def get_active_signal_state(sqlite_path: str, market: str, symbol: str) -> dict | None:
    placeholders = ",".join("?" for _ in ACTIVE_SIGNAL_STATUSES)
    query = f"""
        SELECT * FROM signal_states
        WHERE market = ? AND symbol = ? AND status IN ({placeholders})
        ORDER BY id DESC LIMIT 1
    """
    with _connect(sqlite_path) as conn:
        row = conn.execute(query, (market, symbol, *ACTIVE_SIGNAL_STATUSES)).fetchone()
    return dict(row) if row else None


def get_active_signal_states(sqlite_path: str) -> list[dict]:
    placeholders = ",".join("?" for _ in ACTIVE_SIGNAL_STATUSES)
    query = f"""
        SELECT * FROM signal_states
        WHERE status IN ({placeholders})
        ORDER BY updated_at ASC
    """
    with _connect(sqlite_path) as conn:
        rows = conn.execute(query, ACTIVE_SIGNAL_STATUSES).fetchall()
    return [dict(row) for row in rows]


def get_signal_state_history(
    sqlite_path: str,
    limit: int = 20,
    active_only: bool = False,
    market: str | None = None,
    symbol: str | None = None,
) -> list[dict]:
    conditions = []
    params: list[str | int] = []
    if active_only:
        placeholders = ",".join("?" for _ in ACTIVE_SIGNAL_STATUSES)
        conditions.append(f"status IN ({placeholders})")
        params.extend(ACTIVE_SIGNAL_STATUSES)
    if market:
        conditions.append("market = ?")
        params.append(market)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM signal_states
            {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def create_signal_state(sqlite_path: str, candidate: SignalCandidate, trade_plan: TradePlan) -> int:
    snap = candidate.snapshot
    now = datetime.now(KST).isoformat(timespec="seconds")
    with _connect(sqlite_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO signal_states (
                created_at, updated_at, market, symbol, name, status,
                entry_price, current_price, target_price, stop_price,
                last_alert_price, score, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                now,
                snap.market,
                snap.symbol,
                snap.name,
                "WATCHING",
                trade_plan.entry_price,
                snap.price,
                trade_plan.target_price,
                trade_plan.stop_price,
                snap.price,
                candidate.score,
                json.dumps(candidate.to_dict(), ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_signal_state(
    sqlite_path: str,
    state_id: int,
    status: str,
    current_price: float,
    last_alert_price: float | None = None,
) -> None:
    now = datetime.now(KST).isoformat(timespec="seconds")
    if last_alert_price is None:
        last_alert_price = current_price
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            UPDATE signal_states
            SET updated_at = ?, status = ?, current_price = ?, last_alert_price = ?
            WHERE id = ?
            """,
            (now, status, current_price, last_alert_price, state_id),
        )
        conn.commit()


def clear_signal_states(
    sqlite_path: str,
    market: str | None = None,
    symbol: str | None = None,
    active_only: bool = True,
) -> int:
    conditions = []
    params: list[str] = []
    if active_only:
        placeholders = ",".join("?" for _ in ACTIVE_SIGNAL_STATUSES)
        conditions.append(f"status IN ({placeholders})")
        params.extend(ACTIVE_SIGNAL_STATUSES)
    if market:
        conditions.append("market = ?")
        params.append(market)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    now = datetime.now(KST).isoformat(timespec="seconds")
    with _connect(sqlite_path) as conn:
        cursor = conn.execute(
            f"""
            UPDATE signal_states
            SET updated_at = ?, status = ?
            {where}
            """,
            (now, "CLEARED", *params),
        )
        conn.commit()
        return cursor.rowcount


def get_recent_ai_analysis(
    sqlite_path: str,
    market: str,
    symbol: str,
    ttl_minutes: int,
) -> AIAnalysis | None:
    threshold = datetime.now(KST) - timedelta(minutes=ttl_minutes)
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM ai_analysis_cache
            WHERE market = ? AND symbol = ?
            ORDER BY id DESC LIMIT 1
            """,
            (market, symbol),
        ).fetchone()
    if not row:
        return None
    try:
        created_at = datetime.fromisoformat(row["created_at"])
    except ValueError:
        return None
    if created_at < threshold:
        return None
    return AIAnalysis(
        recommendation=cast(AIRecommendation, row["recommendation"]),
        confidence=int(row["confidence"]),
        summary=row["summary"],
        key_points=json.loads(row["key_points"]),
        risk_notes=json.loads(row["risk_notes"]),
    )


def save_ai_analysis(sqlite_path: str, candidate: SignalCandidate) -> None:
    if candidate.ai_analysis is None:
        return

    snap = candidate.snapshot
    analysis = candidate.ai_analysis
    with _connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO ai_analysis_cache (
                created_at, market, symbol, score, recommendation, confidence,
                summary, key_points, risk_notes, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(KST).isoformat(timespec="seconds"),
                snap.market,
                snap.symbol,
                candidate.score,
                analysis.recommendation,
                analysis.confidence,
                analysis.summary,
                json.dumps(analysis.key_points, ensure_ascii=False),
                json.dumps(analysis.risk_notes, ensure_ascii=False),
                json.dumps(analysis.to_dict(), ensure_ascii=False),
            ),
        )
        conn.commit()


def count_ai_analysis_today(sqlite_path: str) -> int:
    start = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    with _connect(sqlite_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count FROM ai_analysis_cache
            WHERE created_at >= ?
            """,
            (start.isoformat(timespec="seconds"),),
        ).fetchone()
    return int(row["count"] if row else 0)


def parse_outcome_horizons(value: str) -> list[int]:
    horizons = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            minutes = int(item)
        except ValueError:
            continue
        if minutes > 0 and minutes not in horizons:
            horizons.append(minutes)
    return horizons or [5, 15, 30, 60]


def create_signal_outcomes(
    sqlite_path: str,
    state_id: int,
    candidate: SignalCandidate,
    horizons_minutes: list[int],
) -> None:
    snap = candidate.snapshot
    now = datetime.now(KST)
    with _connect(sqlite_path) as conn:
        for horizon in horizons_minutes:
            due_at = now + timedelta(minutes=horizon)
            conn.execute(
                """
                INSERT OR IGNORE INTO signal_outcomes (
                    state_id, created_at, due_at, checked_at, market, symbol, name,
                    horizon_minutes, entry_price, observed_price, pnl_pct, status, raw_json
                ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                """,
                (
                    state_id,
                    now.isoformat(timespec="seconds"),
                    due_at.isoformat(timespec="seconds"),
                    snap.market,
                    snap.symbol,
                    snap.name,
                    horizon,
                    snap.price,
                    "PENDING",
                    json.dumps(candidate.to_dict(), ensure_ascii=False),
                ),
            )
        conn.commit()


def get_due_signal_outcomes(sqlite_path: str, limit: int = 20) -> list[dict]:
    now = datetime.now(KST).isoformat(timespec="seconds")
    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM signal_outcomes
            WHERE status = ? AND due_at <= ?
            ORDER BY due_at ASC
            LIMIT ?
            """,
            ("PENDING", now, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def update_signal_outcome(sqlite_path: str, outcome_id: int, observed_price: float) -> None:
    now = datetime.now(KST).isoformat(timespec="seconds")
    with _connect(sqlite_path) as conn:
        row = conn.execute("SELECT entry_price FROM signal_outcomes WHERE id = ?", (outcome_id,)).fetchone()
        if not row:
            return
        entry_price = float(row["entry_price"])
        pnl_pct = ((observed_price - entry_price) / entry_price) * 100 if entry_price else 0
        conn.execute(
            """
            UPDATE signal_outcomes
            SET checked_at = ?, observed_price = ?, pnl_pct = ?, status = ?
            WHERE id = ?
            """,
            (now, observed_price, pnl_pct, "CHECKED", outcome_id),
        )
        conn.commit()


def get_signal_outcome_history(
    sqlite_path: str,
    limit: int = 20,
    market: str | None = None,
    symbol: str | None = None,
) -> list[dict]:
    conditions = []
    params: list[str | int] = []
    if market:
        conditions.append("market = ?")
        params.append(market)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM signal_outcomes
            {where}
            ORDER BY created_at DESC, horizon_minutes ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_signal_outcome_summary(
    sqlite_path: str,
    days: int = 7,
    market: str | None = None,
    symbol: str | None = None,
) -> list[dict]:
    threshold = datetime.now(KST) - timedelta(days=max(days, 1))
    conditions = ["created_at >= ?", "status = ?", "entry_price > 0", "observed_price > 0"]
    params: list[str] = [threshold.isoformat(timespec="seconds"), "CHECKED"]
    if market:
        conditions.append("market = ?")
        params.append(market)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    where = f"WHERE {' AND '.join(conditions)}"

    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                horizon_minutes,
                COUNT(*) AS total_count,
                SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) AS win_count,
                AVG(pnl_pct) AS avg_pnl_pct,
                MAX(pnl_pct) AS best_pnl_pct,
                MIN(pnl_pct) AS worst_pnl_pct
            FROM signal_outcomes
            {where}
            GROUP BY horizon_minutes
            ORDER BY horizon_minutes ASC
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


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


def get_training_dataset_rows(
    sqlite_path: str,
    days: int = 30,
    market: str | None = None,
    symbol: str | None = None,
) -> list[dict]:
    threshold = datetime.now(KST) - timedelta(days=max(days, 1))
    conditions = [
        "created_at >= ?",
        "status = ?",
        "entry_price > 0",
        "observed_price > 0",
        "pnl_pct IS NOT NULL",
    ]
    params: list[str] = [threshold.isoformat(timespec="seconds"), "CHECKED"]
    if market:
        conditions.append("market = ?")
        params.append(market)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    where = f"WHERE {' AND '.join(conditions)}"

    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM signal_outcomes
            {where}
            ORDER BY created_at ASC, horizon_minutes ASC
            """,
            params,
        ).fetchall()

    return [_build_training_row(dict(row)) for row in rows]


def _build_training_row(outcome: dict) -> dict:
    payload = _load_json_dict(outcome.get("raw_json"))
    snapshot = _load_json_dict(payload.get("snapshot"))
    ai_analysis = _load_json_dict(payload.get("ai_analysis"))
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    risks = payload.get("risks") if isinstance(payload.get("risks"), list) else []

    entry_price = float(outcome["entry_price"])
    observed_price = float(outcome["observed_price"])
    pnl_pct = float(outcome["pnl_pct"])
    price = _float_or_none(snapshot.get("price"))
    open_price = _float_or_none(snapshot.get("open_price"))
    high_price = _float_or_none(snapshot.get("high_price"))
    vwap_price = _float_or_none(snapshot.get("vwap_price"))

    return {
        "created_at": outcome["created_at"],
        "checked_at": outcome["checked_at"],
        "horizon_minutes": int(outcome["horizon_minutes"]),
        "market": outcome["market"],
        "symbol": outcome["symbol"],
        "name": outcome["name"],
        "entry_price": entry_price,
        "observed_price": observed_price,
        "pnl_pct": pnl_pct,
        "label_profit_1pct": 1 if pnl_pct >= 1.0 else 0,
        "label_profit_3pct": 1 if pnl_pct >= 3.0 else 0,
        "label_profit_5pct": 1 if pnl_pct >= 5.0 else 0,
        "label_loss_3pct": 1 if pnl_pct <= -3.0 else 0,
        "candidate_score": int(payload.get("score") or 0),
        "price": price,
        "change_pct": _float_or_none(snapshot.get("change_pct")),
        "volume_ratio": _float_or_none(snapshot.get("volume_ratio")),
        "trading_value_krw": _float_or_none(snapshot.get("trading_value_krw")),
        "vi_gap_pct": _float_or_none(snapshot.get("vi_gap_pct")),
        "open_price": open_price,
        "high_price": high_price,
        "low_price": _float_or_none(snapshot.get("low_price")),
        "vwap_price": vwap_price,
        "vwap_gap_pct": _pct_gap(price, vwap_price),
        "open_gap_pct": _pct_gap(price, open_price),
        "pullback_from_high_pct": _pullback_from_high(price, high_price),
        "foreign_flow_score": _float_or_none(snapshot.get("foreign_flow_score")),
        "institution_flow_score": _float_or_none(snapshot.get("institution_flow_score")),
        "program_flow_score": _float_or_none(snapshot.get("program_flow_score")),
        "news_score": _float_or_none(snapshot.get("news_score")),
        "disclosure_risk": _float_or_none(snapshot.get("disclosure_risk")),
        "exchange": snapshot.get("exchange") or "",
        "ai_recommendation": ai_analysis.get("recommendation") or "",
        "ai_confidence": int(ai_analysis.get("confidence") or 0),
        "reason_count": len(reasons),
        "risk_count": len(risks),
        "reasons": " | ".join(str(item) for item in reasons),
        "risks": " | ".join(str(item) for item in risks),
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


def _float_or_none(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_gap(left: float | None, right: float | None) -> float | None:
    if left is None or right is None or right == 0:
        return None
    return ((left - right) / right) * 100


def _pullback_from_high(price: float | None, high_price: float | None) -> float | None:
    if price is None or high_price is None or high_price == 0:
        return None
    return ((high_price - price) / high_price) * 100


def get_ai_analysis_history(
    sqlite_path: str,
    limit: int = 20,
    market: str | None = None,
    symbol: str | None = None,
) -> list[dict]:
    conditions = []
    params: list[str | int] = []
    if market:
        conditions.append("market = ?")
        params.append(market)
    if symbol:
        conditions.append("symbol = ?")
        params.append(symbol)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with _connect(sqlite_path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM ai_analysis_cache
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]
