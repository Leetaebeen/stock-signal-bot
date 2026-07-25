from datetime import datetime, timedelta

from app.brokers.kis_client import OrderResult
from app.trading.executor import ExecutionConfig, TradingExecutor
from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, StrategyRules


class FakeBroker:
    def __init__(self) -> None:
        self.orders = []

    def place_domestic_order(self, **kwargs):
        self.orders.append(kwargs)
        return OrderResult(
            market="KR",
            side=kwargs["side"],
            symbol=kwargs["symbol"],
            quantity=kwargs["quantity"],
            price=kwargs["price"],
            session="regular",
            order_no=f"order-{len(self.orders)}",
            message="accepted",
            raw={"rt_cd": "0"},
        )

    def place_overseas_order(self, **kwargs):
        self.orders.append(kwargs)
        return OrderResult(
            market="US",
            side=kwargs["side"],
            symbol=kwargs["symbol"],
            quantity=kwargs["quantity"],
            price=kwargs["price"],
            session=kwargs["session"],
            order_no=f"order-{len(self.orders)}",
            message="accepted",
            raw={"rt_cd": "0"},
        )


class FakeAlerter:
    def __init__(self) -> None:
        self.messages = []

    def send(self, message: str) -> bool:
        self.messages.append(message)
        return True


def test_executor_buys_and_stores_position(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    executor = _executor(tmp_path, broker=broker, alerter=alerter)

    result = executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US"))

    assert result.action == "BUY"
    assert broker.orders[0]["side"] == "buy"
    assert broker.orders[0]["session"] == "regular"
    assert "[모의 매수 체결]" in alerter.messages[0]


def test_executor_buys_kr_signal_with_domestic_order(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    executor = _executor(tmp_path, broker=broker, alerter=alerter)

    result = executor.handle_signal(_strong_signal("005930", "삼성전자", "KR", price=78000.0))

    assert result.action == "BUY"
    assert broker.orders[0]["symbol"] == "005930"
    assert broker.orders[0]["price"] == 78000
    assert "매수가: 78,000원" in alerter.messages[0]


def test_executor_blocks_new_entry_when_max_open_positions_reached(tmp_path):
    broker = FakeBroker()
    executor = _executor(tmp_path, broker=broker)
    observed_at = datetime.now(KST)

    first = executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US", observed_at=observed_at))
    second = executor.handle_signal(_strong_signal("PLTR", "Palantir", "US", observed_at=observed_at))

    assert first.action == "BUY"
    assert second.action == "HOLD"
    assert "보유 종목" in second.reason
    assert len(broker.orders) == 1


def test_executor_sells_existing_position_on_take_profit(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    store = JsonPositionStore(tmp_path / "positions.json")
    executor = _executor(tmp_path, broker=broker, alerter=alerter, store=store, rules=StrategyRules(take_profit_pct=5.0))
    entry_at = datetime(2026, 7, 6, 22, 30, 0, tzinfo=KST)
    executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US", price=100.0, observed_at=entry_at))

    result = executor.handle_signal(
        MarketSignal("HOOD", "Robinhood", "US", 106.0, 8.0, 7.0, 5_500_000_000, entry_at + timedelta(minutes=5))
    )

    assert result.action == "SELL"
    assert broker.orders[-1]["side"] == "sell"
    assert store.load() == {}
    assert "[모의 매도 체결]" in alerter.messages[-1]


def test_executor_notifies_order_failure(tmp_path):
    class FailingBroker:
        def place_domestic_order(self, **kwargs):
            raise RuntimeError("주문 API 오류")

        def place_overseas_order(self, **kwargs):
            raise RuntimeError("주문 API 오류")

    alerter = FakeAlerter()
    executor = _executor(tmp_path, broker=FailingBroker(), alerter=alerter)

    result = executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US"))

    assert result.action == "ERROR"
    assert "[모의 주문 실패]" in alerter.messages[0]
    assert "주문 API 오류" in alerter.messages[0]


def _strong_signal(
    symbol: str,
    name: str,
    market: str,
    *,
    price: float = 113.0,
    observed_at=None,
) -> MarketSignal:
    return MarketSignal(
        symbol,
        name,
        market,
        price,
        6.5,
        8.0,
        8_000_000_000,
        observed_at or datetime.now(KST),
        one_minute_change_pct=0.6,
        five_minute_change_pct=1.8,
        breakout_pct=0.5,
        vwap_extension_pct=0.8,
        confirmation_bars=12,
    )


def _executor(tmp_path, *, broker, alerter=None, store=None, rules=None):
    return TradingExecutor(
        broker=broker,
        store=store or JsonPositionStore(tmp_path / "positions.json"),
        rules=rules or StrategyRules(),
        config=ExecutionConfig(
            quantity=1,
            order_enabled=True,
            paper_trading_only=True,
            real_trading_enabled=False,
        ),
        alerter=alerter,
    )
