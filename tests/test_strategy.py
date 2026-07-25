from datetime import datetime, timedelta

from app.trading.state import JsonPositionStore, PendingOrder
from app.trading.strategy import KST, MarketSignal, StrategyRules, evaluate_entry, evaluate_exit, open_position


def test_entry_buys_when_momentum_volume_value_and_score_pass():
    signal = MarketSignal(
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        price=200.0,
        change_pct=6.5,
        volume_ratio=8.0,
        trading_value_krw=8_000_000_000,
        one_minute_change_pct=0.6,
        five_minute_change_pct=1.8,
        breakout_pct=0.5,
        vwap_extension_pct=0.8,
        confirmation_bars=12,
    )

    decision = evaluate_entry(signal, StrategyRules())

    assert decision.action == "BUY"
    assert decision.score >= StrategyRules().entry_min_score
    assert "전략 점수" in decision.reason


def test_entry_holds_when_volume_is_too_low():
    signal = MarketSignal(
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        price=200.0,
        change_pct=6.5,
        volume_ratio=1.2,
        trading_value_krw=5_000_000_000,
    )

    decision = evaluate_entry(signal, StrategyRules())

    assert decision.action == "HOLD"
    assert "거래량 배율" in decision.reason


def test_entry_holds_when_move_is_overheated():
    signal = MarketSignal(
        symbol="HOT",
        name="Hot Stock",
        market="US",
        price=20.0,
        change_pct=70.0,
        volume_ratio=8.0,
        trading_value_krw=5_000_000_000,
    )

    decision = evaluate_entry(signal, StrategyRules())

    assert decision.action == "HOLD"
    assert "과열 기준 초과" in decision.reason


def test_entry_holds_when_strategy_score_is_too_low():
    signal = MarketSignal(
        symbol="SLOW",
        name="Slow Stock",
        market="US",
        price=20.0,
        change_pct=3.2,
        volume_ratio=4.2,
        trading_value_krw=1_100_000_000,
        one_minute_change_pct=0.2,
        five_minute_change_pct=0.6,
        breakout_pct=0.05,
        vwap_extension_pct=2.4,
        confirmation_bars=12,
    )

    decision = evaluate_entry(signal, StrategyRules(entry_min_score=80))

    assert decision.action == "HOLD"
    assert "전략 점수" in decision.reason


def test_exit_sells_at_take_profit():
    entry_at = datetime(2026, 7, 5, 10, 0, 0, tzinfo=KST)
    position = open_position(
        MarketSignal(
            symbol="NVDA",
            name="NVIDIA",
            market="US",
            price=100.0,
            change_pct=5.0,
            volume_ratio=5.0,
            trading_value_krw=3_000_000_000,
            observed_at=entry_at,
        ),
        quantity=1,
    )

    decision = evaluate_exit(position, current_price=105.5, now=entry_at + timedelta(minutes=3), rules=StrategyRules())

    assert decision.action == "SELL"
    assert "익절 기준 도달" in decision.reason


def test_exit_sells_at_stop_loss():
    entry_at = datetime(2026, 7, 5, 10, 0, 0, tzinfo=KST)
    position = open_position(
        MarketSignal("NVDA", "NVIDIA", "US", 100.0, 5.0, 5.0, 3_000_000_000, entry_at),
        quantity=1,
    )

    decision = evaluate_exit(position, current_price=97.8, now=entry_at + timedelta(minutes=3), rules=StrategyRules())

    assert decision.action == "SELL"
    assert "손절 기준 도달" in decision.reason


def test_exit_sells_on_trailing_drawdown():
    entry_at = datetime(2026, 7, 5, 10, 0, 0, tzinfo=KST)
    position = open_position(
        MarketSignal("NVDA", "NVIDIA", "US", 100.0, 5.0, 5.0, 3_000_000_000, entry_at),
        quantity=1,
    ).with_price(104.0)

    decision = evaluate_exit(position, current_price=102.0, now=entry_at + timedelta(minutes=4), rules=StrategyRules())

    assert decision.action == "SELL"
    assert "상승 후 트레일링" in decision.reason


def test_position_store_round_trips(tmp_path):
    entry_at = datetime(2026, 7, 5, 10, 0, 0, tzinfo=KST)
    position = open_position(
        MarketSignal(
            "005930",
            "삼성전자",
            "KR",
            78000.0,
            4.0,
            6.0,
            2_000_000_000,
            entry_at,
            exchange="KRX",
        ),
        quantity=2,
    )
    store = JsonPositionStore(tmp_path / "positions.json")

    store.upsert(position)
    loaded = store.load()
    removed = store.remove("005930")

    assert loaded["005930"].name == "삼성전자"
    assert loaded["005930"].entry_price == 78000.0
    assert loaded["005930"].exchange == "KRX"
    assert removed is not None
    assert store.load() == {}


def test_position_store_preserves_pending_orders_when_positions_change(tmp_path):
    submitted_at = datetime(2026, 7, 25, 10, 0, 0, tzinfo=KST)
    store = JsonPositionStore(tmp_path / "positions.json")
    order = PendingOrder(
        order_no="000001",
        market="KR",
        side="buy",
        symbol="005930",
        name="삼성전자",
        quantity=1,
        requested_price=78000,
        submitted_at=submitted_at,
        reason="test",
        exchange="KRX",
    )

    store.add_pending_order(order)
    store.save({})

    assert store.load_pending_orders() == [order]
    assert store.remove_pending_order("000001") == order
    assert store.load_pending_orders() == []
