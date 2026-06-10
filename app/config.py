from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Stock Signal Bot"
    environment: str = "local"
    market_mode: str = "kis_rank"
    sqlite_path: str = "data/signals.db"

    scan_interval_seconds: int = 60
    min_alert_score: int = 65
    alert_cooldown_minutes: int = 30
    kis_request_interval_seconds: float = 1.1
    kis_rank_count: int = 20

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    kis_app_key: str | None = None
    kis_app_secret: str | None = None
    kis_account_no: str | None = None
    kis_env: str = "paper"
    kis_token_cache_path: str = "data/kis_token.json"

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
