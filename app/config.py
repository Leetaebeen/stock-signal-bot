from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Stock Signal Bot"
    environment: str = "local"
    market_mode: str = "kis_rank"
    enabled_markets: str = "US"
    sqlite_path: str = "data/signals.db"

    scan_interval_seconds: int = 60
    min_alert_score: int = 65
    alert_cooldown_minutes: int = 30
    kis_request_interval_seconds: float = 1.1
    kis_rank_count: int = 20

    us_filter_volume_ratio_min: float = 2.0
    us_filter_volume_ratio_max: float = 20.0
    us_filter_change_pct_min: float = 2.0
    us_filter_change_pct_max: float = 12.0
    us_filter_min_trading_value_krw: float = 500_000_000
    us_filter_min_price: float = 2.0

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    kis_app_key: str | None = None
    kis_app_secret: str | None = None
    kis_account_no: str | None = None
    kis_env: str = "paper"
    kis_token_cache_path: str = "data/kis_token.json"

    toss_api_key: str | None = None
    toss_secret_key: str | None = None
    toss_base_url: str | None = "https://openapi.tossinvest.com"
    toss_token_cache_path: str = "data/toss_token.json"
    toss_scan_cursor_path: str = "data/toss_scan_cursor.txt"
    toss_spike_cache_path: str = "data/toss_price_cache.json"
    toss_request_interval_seconds: float = 1.1
    toss_rank_count: int = 40
    toss_price_sweep_count: int = 0
    toss_spike_1m_pct: float = 3.0
    toss_spike_5m_pct: float = 8.0
    toss_spike_20m_pct: float = 15.0
    toss_spike_max_candidates: int = 20
    us_symbols_path: str | None = "data/us_symbols.txt"

    dart_api_key: str | None = None
    sec_user_agent: str = "stock-signal-bot/0.1 your-email@example.com"

    ai_analysis_enabled: bool = False
    ai_analysis_required: bool = False
    ai_provider: str = "anthropic"
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_min_confidence: int = 70
    ai_timeout_seconds: float = 60.0
    ai_min_rule_score: int = 85
    ai_cache_ttl_minutes: int = 60
    ai_daily_limit: int = 100
    outcome_horizon_minutes: str = "5,15,30,60"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def parse_enabled_markets(value: str) -> set[str]:
    markets = {item.strip().upper() for item in value.split(",") if item.strip()}
    allowed = {"KR", "US"}
    selected = markets & allowed
    return selected or {"US"}
