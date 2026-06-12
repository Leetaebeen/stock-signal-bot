import urllib.parse

import httpx

from app.brokers.toss_auth import TossAuthClient


def test_toss_auth_issues_and_caches_token(tmp_path):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        body = urllib.parse.parse_qs(request.content.decode())
        assert request.url.path == "/oauth2/token"
        assert body["grant_type"] == ["client_credentials"]
        assert body["client_id"] == ["api-key"]
        assert body["client_secret"] == ["secret-key"]
        return httpx.Response(
            200,
            json={
                "access_token": "sample-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    client = TossAuthClient(
        api_key="api-key",
        secret_key="secret-key",
        base_url="https://example.test",
        token_cache_path=str(tmp_path / "toss_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    issued = client.get_access_token()
    cached = client.get_access_token()

    assert issued.access_token == "sample-access-token"
    assert cached.access_token == "sample-access-token"
    assert calls["count"] == 1


def test_toss_auth_requires_keys(tmp_path):
    client = TossAuthClient(
        api_key=None,
        secret_key=None,
        base_url="https://example.test",
        token_cache_path=str(tmp_path / "toss_token.json"),
    )

    try:
        client.issue_access_token()
    except ValueError as exc:
        assert "TOSS_API_KEY" in str(exc)
    else:
        raise AssertionError("expected ValueError")
