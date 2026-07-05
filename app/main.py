from app.config import get_settings


def main() -> None:
    settings = get_settings()
    print(settings.app_name)
    print(f"environment={settings.environment}")
    print(f"kis_env={settings.kis_env}")
    print(f"order_enabled={settings.order_enabled}")
    print(f"real_trading_enabled={settings.real_trading_enabled}")


if __name__ == "__main__":
    main()
