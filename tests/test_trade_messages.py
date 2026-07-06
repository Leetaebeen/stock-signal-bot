from datetime import datetime, timedelta, timezone

from app.alerts.trade_messages import OrderFailure, TradeFill, build_order_failure_message, build_trade_fill_message


KST = timezone(timedelta(hours=9))


def test_build_buy_fill_message():
    message = build_trade_fill_message(
        TradeFill(
            symbol="NVDA",
            name="엔비디아",
            market="US",
            side="BUY",
            quantity=1,
            price=195.2,
            reason="거래량 증가 + 전략 조건 통과",
            filled_at=datetime(2026, 7, 5, 21, 35, 12, tzinfo=KST),
        )
    )

    assert "[모의 매수 체결]" in message
    assert "종목: 엔비디아 (NVDA)" in message
    assert "매수가: $195.20" in message
    assert "주문금액: $195.20" in message


def test_build_sell_fill_message():
    message = build_trade_fill_message(
        TradeFill(
            symbol="NVDA",
            name="엔비디아",
            market="US",
            side="SELL",
            quantity=1,
            price=201.1,
            entry_price=195.2,
            reason="익절 기준 도달",
            holding_seconds=492,
            filled_at=datetime(2026, 7, 5, 21, 43, 24, tzinfo=KST),
        )
    )

    assert "[모의 매도 체결]" in message
    assert "매수가: $195.20" in message
    assert "매도가: $201.10" in message
    assert "수익률: +3.02%" in message
    assert "손익: +$5.90" in message
    assert "보유 시간: 8분 12초" in message


def test_build_order_failure_message():
    message = build_order_failure_message(
        OrderFailure(
            symbol="005930",
            name="삼성전자",
            market="KR",
            side="BUY",
            reason="주문 가능 금액 부족",
            failed_at=datetime(2026, 7, 5, 10, 1, 2, tzinfo=KST),
        )
    )

    assert "[모의 주문 실패]" in message
    assert "시장: 국장" in message
    assert "주문: 매수" in message
    assert "사유: 주문 가능 금액 부족" in message
