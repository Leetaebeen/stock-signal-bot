from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Stock Paper Trader"
    environment: str = "local"

    kis_env: str = "paper"
    kis_app_key: str | None = None
    kis_app_secret: str | None = None
    kis_account_no: str | None = None
    kis_account_product_code: str | None = None
    kis_token_cache_path: str = "data/kis_token_paper.json"

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_notify_startup: bool = False
    telegram_notify_signals: bool = False
    telegram_notify_trades: bool = True
    telegram_notify_errors: bool = True

    paper_trading_only: bool = True
    order_enabled: bool = False
    real_trading_enabled: bool = False

    trading_state_path: str = "data/paper_positions.json"
    trade_journal_path: str = "data/trades.db"
    signal_journal_enabled: bool = True
    signal_label_max_quotes_per_cycle: int = 5
    signal_label_tolerance_seconds: int = 180
    account_sync_interval_seconds: int = 300
    order_auto_cancel_enabled: bool = True
    order_timeout_seconds: int = 120
    order_cancel_max_attempts: int = 3
    pending_order_expiry_seconds: int = 12 * 60 * 60
    trading_default_quantity: int = 1
    trading_max_open_positions: int = 1
    buying_power_check_enabled: bool = True
    max_entries_per_market_24h: int = 1
    kr_max_realized_loss_24h_krw: float = 100_000
    us_max_realized_loss_24h_usd: float = 100
    symbol_reentry_cooldown_seconds: int = 600
    entry_min_change_pct: float = 3.0
    entry_max_change_pct: float = 30.0
    entry_min_volume_ratio: float = 4.0
    entry_max_volume_ratio: float = 20.0
    entry_min_trading_value_krw: float = 1_000_000_000
    entry_min_score: int = 65
    entry_min_confirmation_bars: int = 8
    entry_min_one_minute_change_pct: float = 0.15
    entry_max_one_minute_change_pct: float = 2.5
    entry_min_five_minute_change_pct: float = 0.5
    entry_max_five_minute_change_pct: float = 5.0
    entry_min_breakout_pct: float = 0.0
    entry_max_vwap_extension_pct: float = 2.5
    take_profit_pct: float = 5.0
    stop_loss_pct: float = -2.0
    trailing_start_pct: float = 3.0
    trailing_drawdown_pct: float = 1.5
    max_hold_seconds: int = 1800

    auto_trading_enabled: bool = False
    scan_interval_seconds: int = 60
    scan_candidate_limit: int = 5
    dynamic_universe_enabled: bool = True
    dynamic_universe_refresh_seconds: int = 300
    dynamic_kr_symbol_limit: int = 20
    dynamic_us_symbol_limit_per_exchange: int = 10
    dynamic_us_exchanges: str = "NAS,NYS,AMS"
    market_holiday_check_enabled: bool = True
    market_holiday_cache_seconds: int = 21600
    learning_min_labeled_samples: int = 200
    learning_min_distinct_days: int = 20
    learning_min_distinct_symbols: int = 10
    model_target_return_pct: float = 0.5
    model_round_trip_cost_pct: float = 0.2
    model_min_precision_pct: float = 55.0
    model_min_test_picks: int = 20
    model_walk_forward_folds: int = 3
    model_auto_evaluate_enabled: bool = True
    model_runtime_filter_enabled: bool = True
    model_evaluation_hour_kst: int = 17
    model_training_dataset_path: str = "data/training_signals.csv"
    model_output_path: str = "data/momentum_model.json"
    feature_report_output_path: str = "data/early_surge_report.json"
    feature_report_min_bucket_samples: int = 30
    feature_report_min_distinct_days: int = 5
    feature_report_min_distinct_symbols: int = 5
    us_scan_batch_size: int = 20
    kr_scan_batch_size: int = 10
    us_scan_symbols: str = (
        "NVDA,TSLA,AMD,PLTR,HOOD,SOFI,COIN,MARA,RIOT,IONQ,RKLB,SMCI,MSTR,AVGO,META,MSFT,AAPL,"
        "GOOGL,AMZN,NFLX,ARM,CRWD,DDOG,NET,SHOP,MRVL,MU,INTC,QCOM,ADBE,APP,UPST,AFRM,ROKU,LCID,"
        "RIVN,WBD,OPEN,TQQQ,SQQQ,UBER,ABNB,DKNG,GM,CHWY,SNOW,PATH,U,AI,CVNA,SE,ELF,CELH,DELL"
    )
    us_scan_symbols_path: str | None = None
    us_symbol_exchanges: str = (
        "IONQ:NYS,NET:NYS,UBER:NYS,GM:NYS,CHWY:NYS,SNOW:NYS,PATH:NYS,U:NYS,AI:NYS,"
        "CVNA:NYS,SE:NYS,ELF:NYS,DELL:NYS"
    )
    kr_scan_symbols: str = (
        "005930,000660,035420,035720,005380,068270,247540,086520,028300,196170,277810,042700,"
        "010140,009540,329180,402340,373220,006400,051910,096770,005490,034020,011200,010130,"
        "064350,012450,272210,066570,207940,003670,090430,352820,259960,000270,105560,055550,"
        "316140,138040,323410,122870,298040,042660,267260,005070,005420,128940,161890,112040"
    )
    kr_scan_symbols_path: str | None = None
    quote_request_delay_seconds: float = 1.1
    us_order_exchange: str = "NAS"
    us_order_session: str = "regular"
    allow_kr_regular_trading: bool = True
    allow_us_regular_trading: bool = True
    allow_us_extended_trading: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
