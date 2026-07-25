from datetime import datetime, timedelta

from app.trading.journal import FillRecord, SignalRecord, TradeJournal
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


def test_trade_journal_labels_signal_only_inside_target_window(tmp_path):
    journal = TradeJournal(tmp_path / "trades.db")
    observed_at = datetime(2026, 7, 25, 22, 30, tzinfo=KST)
    observation_id = journal.record_signal(
        SignalRecord(
            symbol="NVDA",
            name="NVIDIA",
            market="US",
            exchange="NAS",
            observed_at=observed_at,
            price=100,
            change_pct=6,
            volume_ratio=5,
            trading_value_krw=5_000_000_000,
            one_minute_change_pct=0.5,
            five_minute_change_pct=1.5,
            breakout_pct=0.4,
            vwap_extension_pct=0.8,
            confirmation_bars=12,
            score=78,
            source="test",
            strategy_action="BUY",
            strategy_reason="strong",
            execution_action="SUBMITTED",
            execution_reason="accepted",
        )
    )

    too_early = journal.due_signal_labels(observed_at + timedelta(minutes=4, seconds=59))
    due = journal.due_signal_labels(observed_at + timedelta(minutes=5, seconds=30))

    assert too_early == []
    assert len(due) == 1
    assert due[0].observation_id == observation_id
    assert due[0].horizon_minutes == 5
    assert journal.update_signal_label(
        due[0],
        current_price=103,
        labeled_at=observed_at + timedelta(minutes=5, seconds=30),
    )
    summary = journal.signal_summary()
    assert summary["observations"] == 1
    assert summary["labeled_5m"] == 1
    assert summary["average_return_5m"] == 3
