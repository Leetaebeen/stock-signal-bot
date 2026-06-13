from app.alerts.message_builder import build_scan_start_message, build_signal_message
from app.models import MarketSnapshot
from app.signals.scorer import score_snapshot


def test_scan_start_message_is_korean_us_alert():
    message = build_scan_start_message("US")

    assert "[US 감시 시작]" in message
    assert "급등주 포착 알림을 시작합니다." in message
    assert "자동주문은 실행하지 않습니다." in message


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


def test_zero_price_is_not_rendered_as_zero_won():
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="NVDA",
            name="엔비디아",
            market="US",
            price=0,
            change_pct=0,
            volume_ratio=3.0,
            trading_value_krw=10_000_000_000,
        )
    )

    message = build_signal_message(candidate)

    assert "현재가: 가격 확인 실패" in message
    assert "0원" not in message
