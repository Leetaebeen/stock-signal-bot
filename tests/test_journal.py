from datetime import datetime

from app.trading.journal import FillRecord, TradeJournal
from app.trading.strategy import KST


def test_trade_journal_records_unique_fills_and_summarizes_sell_results(tmp_path):
    journal = TradeJournal(tmp_path / "trades.db")
    filled_at = datetime(2026, 7, 25, 22, 30, tzinfo=KST)
    buy = FillRecord(
        order_no="buy-1",
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        side="BUY",
        quantity=1,
        price=100,
        currency="USD",
        reason="entry",
        filled_at=filled_at,
    )
    sell = FillRecord(
        order_no="sell-1",
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        side="SELL",
        quantity=1,
        price=105,
        entry_price=100,
        currency="USD",
        reason="take profit",
        filled_at=filled_at,
    )

    assert journal.record_fill(buy) is True
    assert journal.record_fill(sell) is True
    assert journal.record_fill(sell) is False

    summary = journal.performance_summary()["USD"]
    assert summary["trades"] == 1
    assert summary["wins"] == 1
    assert summary["realized_pnl"] == 5
    assert summary["average_pnl_pct"] == 5
