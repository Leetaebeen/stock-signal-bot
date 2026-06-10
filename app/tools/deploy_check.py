from pathlib import Path

from app.config import get_settings


SECRET_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "DART_API_KEY",
    "AI_API_KEY",
)

SENSITIVE_PATHS = (
    ".env",
    "data/kis_token.json",
    "data/kis_token_real.json",
    "data/kis_token_paper.json",
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
    print(f"- kis_env={settings.kis_env}")
    print(f"- scan_interval_seconds={settings.scan_interval_seconds}")
    print(f"- min_alert_score={settings.min_alert_score}")
    print(f"- ai_enabled={settings.ai_analysis_enabled}")
    print(f"- ai_provider={settings.ai_provider}")
    print(f"- ai_model={settings.ai_model or 'default'}")
    print("")
    print("secret_env:")
    for key in SECRET_KEYS:
        value = getattr(settings, _settings_name(key), None)
        print(f"- {key}={'set' if value else 'missing'}")
    print("")
    print("local_sensitive_files:")
    for relative_path in SENSITIVE_PATHS:
        path = root / relative_path
        print(f"- {relative_path}={'exists' if path.exists() else 'missing'}")
    print("")
    print("deploy_notes:")
    print("- Do not upload .env, token cache files, logs, or local SQLite DB unless intentionally migrating state.")
    print("- On the server, create a fresh .env from .env.example and paste secrets there.")
    print("- Run python -m app.tools.kis_auth_check on the server to create a fresh KIS token cache.")
    print("- Run python -m app.tools.ai_check on the server to verify Gemini.")


def _settings_name(env_key: str) -> str:
    return env_key.lower()


if __name__ == "__main__":
    main()
