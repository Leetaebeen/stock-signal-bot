import json

import httpx

from app.brokers.kis_auth import KisAuthClient, _parse_expires_at


def test_kis_auth_issues_and_caches_token(tmp_path):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        payload = json.loads(request.content.decode())
        assert request.url.path == "/oauth2/tokenP"
        assert payload["grant_type"] == "client_credentials"
        assert payload["appkey"] == "app-key"
        assert payload["appsecret"] == "app-secret"
        return httpx.Response(
            200,
            json={
                "access_token": "sample-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    client = KisAuthClient(
        app_key="app-key",
        app_secret="app-secret",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    issued = client.get_access_token()
    cached = client.get_access_token()

    assert issued.access_token == "sample-access-token"
    assert cached.access_token == "sample-access-token"
    assert calls["count"] == 1


def test_kis_auth_requires_keys(tmp_path):
    client = KisAuthClient(
        app_key=None,
        app_secret=None,
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
    )

    try:
        client.issue_access_token()
    except ValueError as exc:
        assert "KIS_APP_KEY" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_default_token_cache_is_separated_by_env(tmp_path):
    paper = KisAuthClient(
        app_key="app-key",
        app_secret="app-secret",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
    )
    real = KisAuthClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
    )

    assert paper.token_cache_path.name == "kis_token_paper.json"
    assert real.token_cache_path.name == "kis_token_real.json"


def test_explicit_kis_expiry_is_parsed_as_kst():
    expires_at = _parse_expires_at({"access_token_token_expired": "2026-06-10 20:30:43"})

    assert expires_at.isoformat() == "2026-06-10T11:30:43+00:00"
