from app.worker import build_start_message


def test_worker_start_message_mentions_paper_trading_status():
    message = build_start_message()

    assert "[KIS 모의투자 봇 시작]" in message
    assert "주문 활성화:" in message
    assert "실거래 활성화:" in message
