from datetime import datetime, timedelta

from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, StrategyRules, evaluate_entry, evaluate_exit, open_position


def test_entry_buys_when_momentum_volume_and_value_pass():
    signal = MarketSignal(
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        price=200.0,
        change_pct=6.5,
        volume_ratio=8.0,
        trading_value_krw=5_000_000_000,
    )

    decision = evaluate_entry(signal, StrategyRules())

    assert decision.action == "BUY"
    assert decision.score > 0
    assert "급등 초입 조건 통과" in decision.reason


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
        MarketSignal("005930", "삼성전자", "KR", 78000.0, 4.0, 6.0, 2_000_000_000, entry_at),
        quantity=2,
    )
    store = JsonPositionStore(tmp_path / "positions.json")

    store.upsert(position)
    loaded = store.load()
    removed = store.remove("005930")

    assert loaded["005930"].name == "삼성전자"
    assert loaded["005930"].entry_price == 78000.0
    assert removed is not None
    assert store.load() == {}
