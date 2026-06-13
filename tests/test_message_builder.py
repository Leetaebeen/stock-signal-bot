from app.alerts.message_builder import (
    build_signal_message,
    build_state_stop_message,
    build_state_target_reached_message,
    build_state_uptrend_message,
)
from app.models import MarketSnapshot
from app.signals.scorer import score_snapshot


def test_signal_message_is_simple_korean_spike_alert():
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="NVDA",
            name="엔비디아",
            market="US",
            price=142.35,
            price_krw=196_443,
            change_pct=5.4,
            volume_ratio=4.8,
            trading_value_krw=120_000_000_000,
            high_price=143.0,
            vwap_price=139.5,
            exchange="NAS",
        )
    )

    message = build_signal_message(candidate)

    assert "[급등주 포착 알림]" in message
    assert "종목명: 엔비디아 (NVDA)" in message
    assert "현재가: 196,443원" in message
    assert "상승률: +5.40%" in message
    assert "거래량: 4.80배" in message
    assert "목표가" not in message
    assert "손절가" not in message
    assert "포착 근거" not in message
    assert "$" not in message


def test_state_followup_messages_are_simple_current_price_alerts():
    state = {
        "market": "US",
        "symbol": "NVDA",
        "name": "엔비디아",
        "last_alert_price": 142.35,
        "target_price": 146.91,
        "stop_price": 138.79,
    }

    uptrend = build_state_uptrend_message(state, current_price=145.12, change_pct=7.21)
    target = build_state_target_reached_message(state, current_price=146.91, change_pct=8.55)
    stopped = build_state_stop_message(state, current_price=138.7, change_pct=1.11)

    for message in (uptrend, target, stopped):
        assert "종목명: 엔비디아 (NVDA)" in message
        assert "현재가:" in message
        assert "상승률:" in message
        assert "목표가" not in message
        assert "손절가" not in message


def test_zero_price_is_not_rendered_as_zero_won():
    state = {
        "market": "US",
        "symbol": "NVDA",
        "name": "엔비디아",
        "last_alert_price": 142.35,
        "target_price": 146.91,
        "stop_price": 138.79,
    }

    stopped = build_state_stop_message(state, current_price=0, change_pct=0)

    assert "현재가: 가격 확인 실패" in stopped
    assert "+0.00%" in stopped
    assert "0원" not in stopped
