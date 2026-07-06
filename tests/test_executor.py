from datetime import datetime, timedelta

from app.brokers.kis_client import OrderResult
from app.trading.executor import ExecutionConfig, TradingExecutor
from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, StrategyRules


class FakeBroker:
    def __init__(self) -> None:
        self.orders = []

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
    executor = TradingExecutor(
        broker=broker,
        store=JsonPositionStore(tmp_path / "positions.json"),
        rules=StrategyRules(),
        config=ExecutionConfig(
            quantity=1,
            order_enabled=True,
            paper_trading_only=True,
            real_trading_enabled=False,
        ),
        alerter=alerter,
    )

    result = executor.handle_signal(
        MarketSignal("HOOD", "Robinhood", "US", 113.0, 6.0, 7.0, 5_000_000_000, datetime.now(KST))
    )

    assert result.action == "BUY"
    assert broker.orders[0]["side"] == "buy"
    assert broker.orders[0]["session"] == "regular"
    assert "[모의 매수 체결]" in alerter.messages[0]


def test_executor_sells_existing_position_on_take_profit(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    store = JsonPositionStore(tmp_path / "positions.json")
    executor = TradingExecutor(
        broker=broker,
        store=store,
        rules=StrategyRules(take_profit_pct=5.0),
        config=ExecutionConfig(
            quantity=1,
            order_enabled=True,
            paper_trading_only=True,
            real_trading_enabled=False,
        ),
        alerter=alerter,
    )
    entry_at = datetime(2026, 7, 6, 22, 30, 0, tzinfo=KST)
    executor.handle_signal(MarketSignal("HOOD", "Robinhood", "US", 100.0, 6.0, 7.0, 5_000_000_000, entry_at))

    result = executor.handle_signal(
        MarketSignal("HOOD", "Robinhood", "US", 106.0, 8.0, 7.0, 5_500_000_000, entry_at + timedelta(minutes=5))
    )

    assert result.action == "SELL"
    assert broker.orders[-1]["side"] == "sell"
    assert store.load() == {}
    assert "[모의 매도 체결]" in alerter.messages[-1]


def test_executor_notifies_order_failure(tmp_path):
    class FailingBroker:
        def place_overseas_order(self, **kwargs):
            raise RuntimeError("장 시작 전")

    alerter = FakeAlerter()
    executor = TradingExecutor(
        broker=FailingBroker(),
        store=JsonPositionStore(tmp_path / "positions.json"),
        rules=StrategyRules(),
        config=ExecutionConfig(
            quantity=1,
            order_enabled=True,
            paper_trading_only=True,
            real_trading_enabled=False,
        ),
        alerter=alerter,
    )

    result = executor.handle_signal(
        MarketSignal("HOOD", "Robinhood", "US", 113.0, 6.0, 7.0, 5_000_000_000, datetime.now(KST))
    )

    assert result.action == "ERROR"
    assert "[모의 주문 실패]" in alerter.messages[0]
    assert "장 시작 전" in alerter.messages[0]
