from app.brokers.kis_auth import KisAuthClient
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    client = KisAuthClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    token = client.get_access_token(force_refresh=True)
    masked = f"{token.access_token[:8]}...{token.access_token[-4:]}"
    print("KIS access token issued.")
    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"token={masked}")
    print(f"expires_at={token.expires_at}")
    print(f"cache={client.token_cache_path}")


if __name__ == "__main__":
    main()
