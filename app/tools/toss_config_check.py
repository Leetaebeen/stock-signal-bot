from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print("toss_config_check")
    print(f"market_mode={settings.market_mode}")
    print(f"toss_api_key={'set' if settings.toss_api_key else 'missing'}")
    print(f"toss_secret_key={'set' if settings.toss_secret_key else 'missing'}")
    print(f"toss_base_url={settings.toss_base_url or 'missing'}")
    print(f"toss_request_interval_seconds={settings.toss_request_interval_seconds}")
    print(f"toss_rank_count={settings.toss_rank_count}")

    if settings.toss_api_key:
        print(f"api_key_prefix={settings.toss_api_key[:9]}...")
    if settings.toss_secret_key:
        print(f"secret_key_prefix={settings.toss_secret_key[:9]}...")

    if not settings.toss_api_key or not settings.toss_secret_key:
        raise SystemExit("TOSS_API_KEY and TOSS_SECRET_KEY are required.")
    if not settings.toss_base_url:
        raise SystemExit("TOSS_BASE_URL is required. Use the official Toss Securities Open API base URL.")


if __name__ == "__main__":
    main()
