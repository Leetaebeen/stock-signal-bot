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
    trading_default_quantity: int = 1
    trading_max_open_positions: int = 1
    entry_min_change_pct: float = 3.0
    entry_max_change_pct: float = 30.0
    entry_min_volume_ratio: float = 4.0
    entry_max_volume_ratio: float = 20.0
    entry_min_trading_value_krw: float = 1_000_000_000
    take_profit_pct: float = 5.0
    stop_loss_pct: float = -2.0
    trailing_start_pct: float = 3.0
    trailing_drawdown_pct: float = 1.5
    max_hold_seconds: int = 1800

    auto_trading_enabled: bool = False
    scan_interval_seconds: int = 60
    scan_candidate_limit: int = 5
    us_scan_batch_size: int = 20
    kr_scan_batch_size: int = 10
    us_scan_symbols: str = "HOOD,NVDA,PLTR,TSLA,AMD,SOXL"
    us_scan_symbols_path: str | None = None
    kr_scan_symbols: str = "005930,000660,035420,035720,005380,068270"
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
