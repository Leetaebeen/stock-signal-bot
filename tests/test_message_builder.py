from app.alerts.message_builder import build_signal_message, build_state_target_reached_message, build_state_uptrend_message
from app.models import MarketSnapshot
from app.signals.scorer import score_snapshot


def test_signal_message_contains_trade_plan_fields():
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

    message = build_signal_message(candidate)

    assert "AI 종목포착 시그널" in message
    assert "포착 종목명: 나우IB (293580)" in message
    assert "적정 매수가:" in message
    assert "포착 현재가:" in message
    assert "목표가:" in message


def test_state_followup_messages_contain_original_plan_prices():
    state = {
        "market": "KR",
        "symbol": "293580",
        "name": "나우IB",
        "last_alert_price": 1629,
        "target_price": 1681,
        "stop_price": 1596,
    }

    uptrend = build_state_uptrend_message(state, current_price=1655, change_pct=5.55)
    target = build_state_target_reached_message(state, current_price=1681, change_pct=7.21)

    assert "상승세 알림" in uptrend
    assert "목표가: 1,681원" in uptrend
    assert "목표가 알림" in target
    assert "1,681원 도달" in target
