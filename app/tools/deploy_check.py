from pathlib import Path

from app.config import get_settings


SECRET_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TOSS_API_KEY",
    "TOSS_SECRET_KEY",
)

SENSITIVE_PATHS = (
    ".env",
    "data/toss_token.json",
    "data/toss_price_cache.json",
    "data/signals.db",
    "logs/stock_signal.log",
    "logs/worker.stdout.log",
    "logs/worker.stderr.log",
)


def main() -> None:
    settings = get_settings()
    root = Path.cwd()

    print("deploy_check")
    print(f"project_root={root}")
    print("")
    print("runtime:")
    print(f"- market_mode={settings.market_mode}")
    print(f"- enabled_markets={settings.enabled_markets}")
    print(f"- scan_interval_seconds={settings.scan_interval_seconds}")
    print(f"- min_alert_score={settings.min_alert_score}")
    print(f"- toss_rank_count={settings.toss_rank_count}")
    print(f"- toss_price_sweep_count={settings.toss_price_sweep_count}")
    print("")
    print("secret_env:")
    for key in SECRET_KEYS:
        value = getattr(settings, key.lower(), None)
        print(f"- {key}={'set' if value else 'missing'}")
    print("")
    print("local_sensitive_files:")
    for relative_path in SENSITIVE_PATHS:
        path = root / relative_path
        print(f"- {relative_path}={'exists' if path.exists() else 'missing'}")
    print("")
    print("deploy_notes:")
    print("- Do not upload .env, token cache files, logs, or local SQLite DB unless intentionally migrating state.")
    print("- Run python -m app.tools.toss_config_check on the server after editing .env.")
    print("- Run python -m app.tools.toss_auth_check on the server to verify Toss IP allowlist and credentials.")


if __name__ == "__main__":
    main()
