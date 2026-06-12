from app.config import Settings


def test_toss_settings_are_loaded_from_env_names():
    settings = Settings(
        toss_api_key="tsck_live_example",
        toss_secret_key="tssk_live_example",
        toss_base_url="https://example.test",
        toss_token_cache_path="data/test_toss_token.json",
        toss_scan_cursor_path="data/test_toss_scan_cursor.txt",
        toss_request_interval_seconds=2.5,
        toss_rank_count=30,
        us_symbols_path="data/test_symbols.txt",
    )

    assert settings.toss_api_key == "tsck_live_example"
    assert settings.toss_secret_key == "tssk_live_example"
    assert settings.toss_base_url == "https://example.test"
    assert settings.toss_token_cache_path == "data/test_toss_token.json"
    assert settings.toss_scan_cursor_path == "data/test_toss_scan_cursor.txt"
    assert settings.toss_request_interval_seconds == 2.5
    assert settings.toss_rank_count == 30
    assert settings.us_symbols_path == "data/test_symbols.txt"
