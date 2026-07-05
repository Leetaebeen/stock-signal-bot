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

    paper_trading_only: bool = True
    order_enabled: bool = False
    real_trading_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
