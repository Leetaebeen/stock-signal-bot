from datetime import datetime, timedelta

from app.brokers.kis_client import BrokerHolding, CancelResult, OrderFillStatus, OrderResult
from app.trading.executor import ExecutionConfig, TradingExecutor
from app.trading.journal import TradeJournal
from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, Position, StrategyRules


class FakeBroker:
    def __init__(self) -> None:
        self.orders = []
        self.fill_state = "FILLED"
        self.holdings = []
        self.cancellations = []

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
            order_org_no="06010",
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
            order_org_no=None,
            message="accepted",
            raw={"rt_cd": "0"},
        )

    def get_order_fill_status(self, **kwargs):
        order = next(item for index, item in enumerate(self.orders, start=1) if f"order-{index}" == kwargs["order_no"])
        return OrderFillStatus(
            state=self.fill_state,
            filled_quantity=float(order["quantity"]) if self.fill_state == "FILLED" else 0.0,
            average_price=float(order["price"]) if self.fill_state == "FILLED" else 0.0,
            raw={},
        )

    def get_holdings(self, market: str) -> list[BrokerHolding]:
        return [item for item in self.holdings if item.market == market]

    def cancel_order(self, **kwargs):
        self.cancellations.append(kwargs)
        return CancelResult(
            market=kwargs["market"],
            symbol=kwargs["symbol"],
            original_order_no=kwargs["order_no"],
            cancel_order_no="cancel-1",
            message="accepted",
            raw={},
        )


class FakeAlerter:
    def __init__(self) -> None:
        self.messages = []

    def send(self, message: str) -> bool:
        self.messages.append(message)
        return True


def test_executor_stores_buy_as_pending_then_confirms_fill(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    executor = _executor(tmp_path, broker=broker, alerter=alerter)

    submitted = executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US"))

    assert submitted.action == "SUBMITTED"
    assert broker.orders[0]["side"] == "buy"
    assert broker.orders[0]["session"] == "regular"
    assert executor.store.load() == {}
    assert len(executor.store.load_pending_orders()) == 1
    assert alerter.messages == []

    result = executor.reconcile_pending_orders()[0]

    assert result.action == "BUY"
    assert executor.store.load()["HOOD"].entry_price == 113.0
    assert executor.store.load_pending_orders() == []
    assert "[모의 매수 체결]" in alerter.messages[0]


def test_executor_buys_kr_signal_with_domestic_order(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    executor = _executor(tmp_path, broker=broker, alerter=alerter)

    submitted = executor.handle_signal(_strong_signal("005930", "삼성전자", "KR", price=78000.0))
    result = executor.reconcile_pending_orders()[0]

    assert submitted.action == "SUBMITTED"
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

    assert first.action == "SUBMITTED"
    assert second.action == "HOLD"
    assert "매수대기" in second.reason
    assert len(broker.orders) == 1


def test_executor_sells_existing_position_on_take_profit(tmp_path):
    broker = FakeBroker()
    alerter = FakeAlerter()
    store = JsonPositionStore(tmp_path / "positions.json")
    executor = _executor(tmp_path, broker=broker, alerter=alerter, store=store, rules=StrategyRules(take_profit_pct=5.0))
    entry_at = datetime(2026, 7, 6, 22, 30, 0, tzinfo=KST)
    executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US", price=100.0, observed_at=entry_at))
    executor.reconcile_pending_orders()

    submitted = executor.handle_signal(
        MarketSignal("HOOD", "Robinhood", "US", 106.0, 8.0, 7.0, 5_500_000_000, entry_at + timedelta(minutes=5))
    )

    assert submitted.action == "SUBMITTED"
    assert "HOOD" in store.load()
    result = executor.reconcile_pending_orders()[0]

    assert result.action == "SELL"
    assert broker.orders[-1]["side"] == "sell"
    assert store.load() == {}
    assert "[모의 매도 체결]" in alerter.messages[-1]


def test_executor_sells_position_when_liquidation_is_requested(tmp_path):
    broker = FakeBroker()
    store = JsonPositionStore(tmp_path / "positions.json")
    store.upsert(
        Position(
            symbol="005930",
            name="Samsung Electronics",
            market="KR",
            quantity=4,
            entry_price=290000,
            entry_at=datetime.now(KST),
            highest_price=290000,
            exchange="KRX",
            managed=True,
            liquidation_requested=True,
        )
    )
    executor = _executor(tmp_path, broker=broker, store=store)

    submitted = executor.handle_signal(
        MarketSignal(
            "005930",
            "Samsung Electronics",
            "KR",
            249500,
            -1,
            0,
            1_000_000_000,
            datetime.now(KST),
            exchange="KRX",
        )
    )

    assert submitted.action == "SUBMITTED"
    assert submitted.reason == "사용자 요청 모의 포지션 정리"
    assert broker.orders[-1]["side"] == "sell"
    assert broker.orders[-1]["quantity"] == 4

    confirmed = executor.reconcile_pending_orders()[0]

    assert confirmed.action == "SELL"
    assert store.load() == {}


def test_executor_does_not_duplicate_order_while_fill_is_pending(tmp_path):
    broker = FakeBroker()
    broker.fill_state = "PENDING"
    executor = _executor(tmp_path, broker=broker)
    signal = _strong_signal("HOOD", "Robinhood", "US")

    first = executor.handle_signal(signal)
    second = executor.handle_signal(signal)
    reconciled = executor.reconcile_pending_orders()[0]

    assert first.action == "SUBMITTED"
    assert second.action == "PENDING"
    assert reconciled.action == "PENDING"
    assert len(broker.orders) == 1


def test_executor_auto_cancels_stale_pending_order_once(tmp_path):
    broker = FakeBroker()
    broker.fill_state = "PENDING"
    executor = _executor(tmp_path, broker=broker)
    signal = _strong_signal(
        "005930",
        "삼성전자",
        "KR",
        price=78000,
        observed_at=datetime.now(KST) - timedelta(minutes=3),
    )

    executor.handle_signal(signal)
    first = executor.reconcile_pending_orders()[0]
    second = executor.reconcile_pending_orders()[0]

    assert first.action == "CANCEL_SUBMITTED"
    assert second.action == "PENDING"
    assert broker.cancellations[0]["order_no"] == "order-1"
    assert broker.cancellations[0]["order_org_no"] == "06010"
    assert len(broker.cancellations) == 1
    assert executor.store.load_pending_orders()[0].cancel_requested_at is not None
    assert executor.store.load_pending_orders()[0].cancel_attempts == 1


def test_executor_does_not_cancel_stale_order_when_market_is_closed(tmp_path):
    broker = FakeBroker()
    broker.fill_state = "PENDING"
    executor = _executor(tmp_path, broker=broker)
    executor.handle_signal(
        _strong_signal(
            "005930",
            "삼성전자",
            "KR",
            price=78000,
            observed_at=datetime.now(KST) - timedelta(minutes=3),
        )
    )

    result = executor.reconcile_pending_orders(cancel_markets=set())[0]

    assert result.action == "PENDING"
    assert broker.cancellations == []


def test_executor_reconciles_broker_holding_into_local_state(tmp_path):
    broker = FakeBroker()
    broker.holdings = [
        BrokerHolding("005930", "삼성전자", "KR", 2, 78000, 79000, "KRX")
    ]
    executor = _executor(tmp_path, broker=broker)

    results = executor.reconcile_holdings("KR")

    position = executor.store.load()["005930"]
    assert results[0].action == "SYNCED"
    assert position.quantity == 2
    assert position.entry_price == 78000
    assert position.managed is False


def test_executor_preserves_liquidation_request_during_holding_sync(tmp_path):
    broker = FakeBroker()
    broker.holdings = [
        BrokerHolding("005930", "Samsung Electronics", "KR", 4, 290000, 249500, "KRX")
    ]
    store = JsonPositionStore(tmp_path / "positions.json")
    store.upsert(
        Position(
            symbol="005930",
            name="Samsung Electronics",
            market="KR",
            quantity=4,
            entry_price=290000,
            entry_at=datetime.now(KST),
            highest_price=290000,
            exchange="KRX",
            managed=True,
            liquidation_requested=True,
        )
    )
    executor = _executor(tmp_path, broker=broker, store=store)

    executor.reconcile_holdings("KR")

    position = store.load()["005930"]
    assert position.managed is True
    assert position.liquidation_requested is True


def test_executor_writes_confirmed_buy_and_sell_to_trade_journal(tmp_path):
    broker = FakeBroker()
    journal = TradeJournal(tmp_path / "trades.db")
    store = JsonPositionStore(tmp_path / "positions.json")
    executor = _executor(
        tmp_path,
        broker=broker,
        store=store,
        journal=journal,
        rules=StrategyRules(take_profit_pct=5.0),
    )
    entry_at = datetime.now(KST)

    executor.handle_signal(_strong_signal("HOOD", "Robinhood", "US", price=100, observed_at=entry_at))
    executor.reconcile_pending_orders()
    executor.handle_signal(
        MarketSignal(
            "HOOD",
            "Robinhood",
            "US",
            106,
            8,
            7,
            5_500_000_000,
            entry_at + timedelta(minutes=5),
        )
    )
    executor.reconcile_pending_orders()

    summary = journal.performance_summary()["USD"]
    assert summary["trades"] == 1
    assert summary["wins"] == 1
    assert summary["realized_pnl"] == 6


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


def _executor(tmp_path, *, broker, alerter=None, store=None, rules=None, journal=None):
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
        journal=journal,
    )
