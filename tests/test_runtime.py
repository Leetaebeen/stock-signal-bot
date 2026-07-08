from app.trading.runtime import TradingRuntime


class FakeSettings:
    kis_app_key = "app-key"
    kis_app_secret = "app-secret"
    kis_account_no = "12345678"
    kis_account_product_code = "01"
    kis_env = "paper"
    kis_token_cache_path = "data/kis_token_paper.json"
    trading_state_path = "data/test_positions.json"
    entry_min_change_pct = 3.0
    entry_max_change_pct = 30.0
    entry_min_volume_ratio = 4.0
    entry_max_volume_ratio = 20.0
    entry_min_trading_value_krw = 1_000_000_000
    take_profit_pct = 5.0
    stop_loss_pct = -2.0
    trailing_start_pct = 3.0
    trailing_drawdown_pct = 1.5
    max_hold_seconds = 1800
    trading_default_quantity = 1
    trading_max_open_positions = 1
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
