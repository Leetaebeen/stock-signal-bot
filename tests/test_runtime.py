from datetime import datetime, timedelta

from app.brokers.kis_client import PriceSnapshot
from app.scanners.momentum import ScanCandidate
from app.trading.executor import ExecutionResult
from app.trading.journal import SignalRecord
from app.trading.runtime import TradingRuntime
from app.trading.strategy import KST, MarketSignal, Position


class FakeSettings:
    kis_app_key = "app-key"
    kis_app_secret = "app-secret"
    kis_account_no = "12345678"
    kis_account_product_code = "01"
    kis_env = "paper"
    kis_token_cache_path = "data/kis_token_paper.json"
    trading_state_path = "data/test_positions.json"
    trade_journal_path = ":memory:"
    signal_journal_enabled = True
    signal_label_max_quotes_per_cycle = 5
    signal_label_tolerance_seconds = 180
    order_auto_cancel_enabled = True
    order_timeout_seconds = 120
    order_cancel_max_attempts = 3
    entry_min_change_pct = 3.0
    entry_max_change_pct = 30.0
    entry_min_volume_ratio = 4.0
    entry_max_volume_ratio = 20.0
    entry_min_trading_value_krw = 1_000_000_000
    entry_min_score = 65
    entry_min_confirmation_bars = 8
    entry_min_one_minute_change_pct = 0.15
    entry_max_one_minute_change_pct = 2.5
    entry_min_five_minute_change_pct = 0.5
    entry_max_five_minute_change_pct = 5.0
    entry_min_breakout_pct = 0.0
    entry_max_vwap_extension_pct = 2.5
    take_profit_pct = 5.0
    stop_loss_pct = -2.0
    trailing_start_pct = 3.0
    trailing_drawdown_pct = 1.5
    max_hold_seconds = 1800
    trading_default_quantity = 1
    trading_max_open_positions = 1
    buying_power_check_enabled = True
    order_enabled = False
    paper_trading_only = True
    real_trading_enabled = False
    us_order_exchange = "NAS"
    us_order_session = "regular"
    telegram_notify_trades = True
    telegram_notify_errors = True
    telegram_enabled = False
    telegram_bot_token = None
    telegram_chat_id = None
    scan_candidate_limit = 5
    us_scan_batch_size = 2
    kr_scan_batch_size = 1
    us_scan_symbols = "NVDA, HOOD, NVDA"
    us_scan_symbols_path = None
    us_symbol_exchanges = "IONQ:NYS"
    kr_scan_symbols = "005930, 000660, 005930"
    kr_scan_symbols_path = None
    quote_request_delay_seconds = 0.0
    allow_kr_regular_trading = True
    allow_us_regular_trading = True
    allow_us_extended_trading = False


def test_runtime_dedupes_us_and_kr_symbols():
    runtime = TradingRuntime(FakeSettings())

    assert runtime._us_symbols() == ["NVDA", "HOOD"]
    assert runtime._kr_symbols() == ["005930", "000660"]


def test_runtime_rotates_us_and_kr_scan_batches():
    runtime = TradingRuntime(FakeSettings())

    assert runtime._next_us_symbols() == ["NVDA", "HOOD"]
    assert runtime._next_us_symbols() == ["NVDA", "HOOD"]
    assert runtime._next_kr_symbols() == ["005930"]
    assert runtime._next_kr_symbols() == ["000660"]
    assert runtime._next_kr_symbols() == ["005930"]


def test_runtime_parses_us_exchange_map():
    runtime = TradingRuntime(FakeSettings())

    assert runtime._us_exchange_map() == {"IONQ": "NYS"}


def test_runtime_monitors_open_position_before_candidate_scan(tmp_path):
    settings = FakeSettings()
    settings.trading_state_path = str(tmp_path / "positions.json")
    runtime = TradingRuntime(settings)
    runtime.store.save(
        {
            "IONQ": Position(
                symbol="IONQ",
                name="IonQ",
                market="US",
                quantity=1,
                entry_price=40.0,
                entry_at=datetime(2026, 7, 24, 22, 30, tzinfo=KST),
                highest_price=41.0,
                exchange="NYS",
            )
        }
    )

    class FakeClient:
        def get_overseas_price(self, symbol, exchange, name):
            assert symbol == "IONQ"
            assert exchange == "NYS"
            return PriceSnapshot("IONQ", name, "US", 41.0, 5.0, 5_000_000_000, "NYS")

    class FakeExecutor:
        def __init__(self):
            self.signals = []

        def handle_signal(self, signal):
            self.signals.append(signal)
            return ExecutionResult("HOLD", signal.symbol, "보유")

    runtime.client = FakeClient()
    runtime.executor = FakeExecutor()

    results = runtime._monitor_open_positions(["US"])

    assert results[0].symbol == "IONQ"
    assert runtime.executor.signals[0].price == 41.0


def test_runtime_does_not_auto_sell_untracked_account_holding(tmp_path):
    settings = FakeSettings()
    settings.trading_state_path = str(tmp_path / "positions.json")
    runtime = TradingRuntime(settings)
    runtime.store.save(
        {
            "005930": Position(
                symbol="005930",
                name="삼성전자",
                market="KR",
                quantity=4,
                entry_price=290000,
                entry_at=datetime.now(KST),
                highest_price=290000,
                exchange="KRX",
                managed=False,
            )
        }
    )

    class FailOnUse:
        def __getattr__(self, name):
            raise AssertionError(f"untracked holding must not call {name}")

    runtime.client = FailOnUse()
    runtime.executor = FailOnUse()

    assert runtime._monitor_open_positions(["KR"]) == []


def test_runtime_monitors_untracked_holding_with_liquidation_request(tmp_path):
    settings = FakeSettings()
    settings.trading_state_path = str(tmp_path / "positions.json")
    runtime = TradingRuntime(settings)
    runtime.store.save(
        {
            "005930": Position(
                symbol="005930",
                name="Samsung Electronics",
                market="KR",
                quantity=4,
                entry_price=290000,
                entry_at=datetime.now(KST),
                highest_price=290000,
                exchange="KRX",
                managed=False,
                liquidation_requested=True,
            )
        }
    )

    class FakeClient:
        def get_domestic_price(self, symbol, name):
            return PriceSnapshot(symbol, name, "KR", 249500, -1, 1_000_000_000, "KRX")

    class FakeExecutor:
        def handle_signal(self, signal):
            return ExecutionResult("SUBMITTED", signal.symbol, "requested", "order-1")

    runtime.client = FakeClient()
    runtime.executor = FakeExecutor()

    results = runtime._monitor_open_positions(["KR"])

    assert results[0].action == "SUBMITTED"


def test_runtime_records_candidate_features_and_execution_result(tmp_path):
    settings = FakeSettings()
    settings.trading_state_path = str(tmp_path / "positions.json")
    settings.trade_journal_path = str(tmp_path / "trades.db")
    runtime = TradingRuntime(settings)
    signal = MarketSignal(
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        price=100,
        change_pct=6,
        volume_ratio=5,
        trading_value_krw=5_000_000_000,
        observed_at=datetime.now(KST),
        exchange="NAS",
        one_minute_change_pct=0.5,
        five_minute_change_pct=1.5,
        breakout_pct=0.4,
        vwap_extension_pct=0.8,
        confirmation_bars=12,
    )

    runtime._record_signal(
        ScanCandidate(signal=signal, source="test", score=78),
        ExecutionResult("SUBMITTED", "NVDA", "accepted", "order-1"),
    )

    summary = runtime.journal.signal_summary()
    assert summary["observations"] == 1


def test_runtime_labels_due_signal_with_current_quote(tmp_path):
    settings = FakeSettings()
    settings.trading_state_path = str(tmp_path / "positions.json")
    settings.trade_journal_path = str(tmp_path / "trades.db")
    runtime = TradingRuntime(settings)
    observed_at = datetime.now(KST).replace(microsecond=0) - timedelta(minutes=5, seconds=30)
    runtime.journal.record_signal(
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
            execution_action="HOLD",
            execution_reason="account limit",
        )
    )

    class FakeClient:
        def get_overseas_price(self, symbol, exchange):
            return PriceSnapshot(symbol, "NVIDIA", "US", 103, 7, 6_000_000_000, exchange)

    runtime.client = FakeClient()
    runtime._label_due_signals(["US"], [])

    summary = runtime.journal.signal_summary()
    assert summary["labeled_5m"] == 1
    assert summary["average_return_5m"] == 3
