import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx


TOSS_DEFAULT_BASE_URL = "https://openapi.tossinvest.com"


@dataclass(frozen=True)
class TossToken:
    access_token: str
    token_type: str
    expires_at: str

    @property
    def authorization(self) -> str:
        if self.token_type.lower() == "bearer":
            return f"Bearer {self.access_token}"
        return f"{self.token_type} {self.access_token}"

    def is_valid(self, min_valid_seconds: int = 300) -> bool:
        try:
            expires_at = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > datetime.now(timezone.utc) + timedelta(seconds=min_valid_seconds)


class TossAuthClient:
    def __init__(
        self,
        api_key: str | None,
        secret_key: str | None,
        base_url: str | None,
        token_cache_path: str = "data/toss_token.json",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = (base_url or TOSS_DEFAULT_BASE_URL).rstrip("/")
        self.token_cache_path = Path(token_cache_path)
        self.http_client = http_client or httpx.Client(timeout=10)

    def get_access_token(self, force_refresh: bool = False) -> TossToken:
        if not force_refresh:
            cached = self._load_cached_token()
            if cached and cached.is_valid():
                return cached
        return self.issue_access_token()

    def issue_access_token(self) -> TossToken:
        if not self.api_key or not self.secret_key:
            raise ValueError("TOSS_API_KEY and TOSS_SECRET_KEY are required.")

        response = self.http_client.post(
            f"{self.base_url}/oauth2/token",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.api_key,
                "client_secret": self.secret_key,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Toss token request failed: {response.status_code} {response.text}")

        token = self._parse_token_response(response.json())
        self._save_cached_token(token)
        return token

    def _parse_token_response(self, payload: dict[str, Any]) -> TossToken:
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError(f"Toss token response has no access_token: {payload}")

        token_type = payload.get("token_type") or "Bearer"
        expires_in = int(payload.get("expires_in") or 24 * 60 * 60)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return TossToken(access_token=access_token, token_type=token_type, expires_at=expires_at.isoformat())

    def _load_cached_token(self) -> TossToken | None:
        if not self.token_cache_path.exists():
            return None
        try:
            payload = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
            return TossToken(**payload)
        except (OSError, TypeError, ValueError):
            return None

    def _save_cached_token(self, token: TossToken) -> None:
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_cache_path.write_text(json.dumps(asdict(token), ensure_ascii=False, indent=2), encoding="utf-8")
