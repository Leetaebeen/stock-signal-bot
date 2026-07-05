from datetime import datetime, timedelta, timezone

import httpx

from app.brokers.kis_auth import KisAuthClient, KisToken


def test_kis_auth_issues_paper_token(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth2/tokenP"
        assert request.url.host == "openapivts.koreainvestment.com"
        return httpx.Response(
            200,
            json={"access_token": "sample-access-token", "token_type": "Bearer", "expires_in": 3600},
        )

    client = KisAuthClient(
        app_key="app-key",
        app_secret="app-secret",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    token = client.get_access_token(force_refresh=True)

    assert token.authorization == "Bearer sample-access-token"
    assert client.token_cache_path.name == "kis_token_paper.json"


def test_kis_token_validity_window():
    token = KisToken(
        access_token="sample-access-token",
        token_type="Bearer",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
    )

    assert token.is_valid()


def test_paper_mode_guard_rejects_real_env(tmp_path):
    client = KisAuthClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
    )

    try:
        client.assert_paper_mode(paper_trading_only=True, real_trading_enabled=False)
    except RuntimeError as exc:
        assert "KIS_ENV" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
