from app.alerts.message_builder import (
    build_signal_message,
    build_state_stop_message,
    build_state_target_reached_message,
    build_state_uptrend_message,
)
from app.models import MarketSnapshot
from app.signals.scorer import score_snapshot


def test_signal_message_contains_trade_plan_fields_in_krw():
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="NVDA",
            name="NVIDIA",
            market="US",
            price=142.35,
            change_pct=5.4,
            volume_ratio=4.8,
            trading_value_krw=120_000_000_000,
            high_price=143.0,
            vwap_price=139.5,
            news_score=0.4,
        )
    )

    message = build_signal_message(candidate)

    assert "AI 종목 포착 시그널" in message
    assert "포착 종목명: NVIDIA (NVDA)" in message
    assert "적정 매수가:" in message
    assert "포착 현재가:" in message
    assert "목표가:" in message
    assert "손절가:" in message
    assert "$" not in message
    assert "원" in message


def test_state_followup_messages_show_target_and_stop_prices_in_krw():
    state = {
        "market": "US",
        "symbol": "NVDA",
        "name": "NVIDIA",
        "last_alert_price": 142.35,
        "target_price": 146.91,
        "stop_price": 138.79,
    }

    uptrend = build_state_uptrend_message(state, current_price=145.12, change_pct=7.21)
    target = build_state_target_reached_message(state, current_price=146.91, change_pct=8.55)
    stopped = build_state_stop_message(state, current_price=138.7, change_pct=1.11)

    assert "상승세 알림" in uptrend
    assert "목표가: 198,329원" in uptrend
    assert "손절가: 187,367원" in uptrend
    assert "목표가 알림" in target
    assert "목표가 198,329원에 도달했습니다." in target
    assert "손절가 이탈" in stopped
    assert "손절가: 187,367원 이탈" in stopped
