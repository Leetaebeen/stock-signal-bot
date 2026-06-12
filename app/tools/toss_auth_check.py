from app.brokers.toss_auth import TossAuthClient
from app.config import get_settings


def main() -> None:
    settings = get_settings()
    client = TossAuthClient(
        api_key=settings.toss_api_key,
        secret_key=settings.toss_secret_key,
        base_url=settings.toss_base_url,
    )
    token = client.get_access_token(force_refresh=True)
    print("Toss access token issued.")
    print(f"base_url={client.base_url}")
    print(f"token={token.access_token[:8]}...{token.access_token[-4:]}")
    print(f"expires_at={token.expires_at}")
    print(f"cache={client.token_cache_path}")


if __name__ == "__main__":
    main()
