from app.db import (
    clear_signal_states,
    create_signal_state,
    create_signal_outcomes,
    get_active_signal_state,
    get_active_signal_states,
    get_due_signal_outcomes,
    get_signal_outcome_history,
    get_signal_outcome_summary,
    get_signal_state_history,
    init_db,
    parse_outcome_horizons,
    update_signal_outcome,
    update_signal_state,
)
from app.models import MarketSnapshot
from app.signals.scorer import score_snapshot
from app.signals.state_machine import evaluate_signal_status
from app.signals.trade_plan import build_trade_plan


def test_signal_state_tracks_active_candidate(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="293580",
            name="나우IB",
            market="KR",
            price=1629,
            change_pct=3.89,
            volume_ratio=5.2,
            trading_value_krw=90_000_000_000,
            vi_gap_pct=1.5,
            high_price=1640,
            vwap_price=1600,
            foreign_flow_score=0.5,
            institution_flow_score=0.5,
            program_flow_score=0.4,
        )
    )
    plan = build_trade_plan(candidate)

    create_signal_state(str(db_path), candidate, plan)
    active = get_active_signal_state(str(db_path), "KR", "293580")

    assert active is not None
    assert active["status"] == "WATCHING"
    assert len(get_active_signal_states(str(db_path))) == 1

    update_signal_state(str(db_path), active["id"], "TARGET_REACHED", plan.target_price)
    assert get_active_signal_state(str(db_path), "KR", "293580") is None
    assert get_active_signal_states(str(db_path)) == []
    assert get_signal_state_history(str(db_path), active_only=True) == []
    assert get_signal_state_history(str(db_path), active_only=False)[0]["status"] == "TARGET_REACHED"


def test_evaluate_signal_status():
    assert evaluate_signal_status(105, 105, 95, 100) == "TARGET_REACHED"
    assert evaluate_signal_status(94, 105, 95, 100) == "STOPPED"
    assert evaluate_signal_status(102, 105, 95, 100) == "UPTREND"
    assert evaluate_signal_status(101, 105, 95, 100) == "WATCHING"


def test_clear_signal_states_marks_active_states_as_cleared(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="293580",
            name="나우IB",
            market="KR",
            price=1629,
            change_pct=3.89,
            volume_ratio=5.2,
            trading_value_krw=90_000_000_000,
        )
    )
    create_signal_state(str(db_path), candidate, build_trade_plan(candidate))

    count = clear_signal_states(str(db_path), symbol="293580")

    assert count == 1
    assert get_active_signal_states(str(db_path)) == []
    history = get_signal_state_history(str(db_path), active_only=False)
    assert history[0]["status"] == "CLEARED"


def test_signal_outcomes_are_scheduled_and_updated(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="293580",
            name="나우IB",
            market="KR",
            price=1629,
            change_pct=3.89,
            volume_ratio=5.2,
            trading_value_krw=90_000_000_000,
        )
    )
    state_id = create_signal_state(str(db_path), candidate, build_trade_plan(candidate))

    create_signal_outcomes(str(db_path), state_id, candidate, [5, 15])
    history = get_signal_outcome_history(str(db_path))

    assert len(history) == 2
    assert get_due_signal_outcomes(str(db_path)) == []
    update_signal_outcome(str(db_path), history[0]["id"], observed_price=1700)
    updated = get_signal_outcome_history(str(db_path), symbol="293580")
    checked = [row for row in updated if row["status"] == "CHECKED"]
    assert len(checked) == 1
    assert checked[0]["pnl_pct"] > 0


def test_signal_outcome_summary_groups_checked_results(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="NVDA",
            name="NVIDIA",
            market="US",
            price=100,
            change_pct=4.5,
            volume_ratio=5.0,
            trading_value_krw=90_000_000_000,
            vwap_price=99,
        )
    )
    state_id = create_signal_state(str(db_path), candidate, build_trade_plan(candidate))

    create_signal_outcomes(str(db_path), state_id, candidate, [5, 15])
    history = get_signal_outcome_history(str(db_path))
    for row in history:
        update_signal_outcome(str(db_path), row["id"], observed_price=105)

    summary = get_signal_outcome_summary(str(db_path), market="US", symbol="NVDA")

    assert [row["horizon_minutes"] for row in summary] == [5, 15]
    assert summary[0]["total_count"] == 1
    assert summary[0]["win_count"] == 1
    assert summary[0]["avg_pnl_pct"] == 5.0


def test_parse_outcome_horizons_ignores_invalid_values():
    assert parse_outcome_horizons("5, 15, nope, 15, 60") == [5, 15, 60]
    assert parse_outcome_horizons("") == [5, 15, 30, 60]
