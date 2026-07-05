import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx


KIS_REAL_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_PAPER_BASE_URL = "https://openapivts.koreainvestment.com:29443"
KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class KisToken:
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


class KisAuthClient:
    def __init__(
        self,
        app_key: str | None,
        app_secret: str | None,
        env: str,
        token_cache_path: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.env = env.strip().lower()
        self.token_cache_path = _resolve_token_cache_path(token_cache_path, self.env)
        self.http_client = http_client or httpx.Client(timeout=10)

    @property
    def base_url(self) -> str:
        if self.env == "real":
            return KIS_REAL_BASE_URL
        return KIS_PAPER_BASE_URL

    def assert_paper_mode(self, paper_trading_only: bool, real_trading_enabled: bool) -> None:
        if self.env != "paper":
            raise RuntimeError("KIS_ENV must be paper.")
        if not paper_trading_only:
            raise RuntimeError("PAPER_TRADING_ONLY must be true.")
        if real_trading_enabled:
            raise RuntimeError("REAL_TRADING_ENABLED must be false.")

    def get_access_token(self, force_refresh: bool = False) -> KisToken:
        if not force_refresh:
            cached = self._load_cached_token()
            if cached and cached.is_valid():
                return cached
        return self.issue_access_token()

    def issue_access_token(self) -> KisToken:
        if not self.app_key or not self.app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET are required.")

        response = self.http_client.post(
            f"{self.base_url}/oauth2/tokenP",
            headers={"content-type": "application/json; charset=utf-8"},
            json={
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS token request failed: {response.status_code} {response.text}")

        token = self._parse_token_response(response.json())
        self._save_cached_token(token)
        return token

    def _parse_token_response(self, payload: dict[str, Any]) -> KisToken:
        access_token = payload.get("access_token")
        if not access_token:
            raise RuntimeError(f"KIS token response has no access_token: {payload}")

        token_type = payload.get("token_type") or "Bearer"
        expires_at = _parse_expires_at(payload)
        return KisToken(access_token=access_token, token_type=token_type, expires_at=expires_at.isoformat())

    def _load_cached_token(self) -> KisToken | None:
        if not self.token_cache_path.exists():
            return None
        try:
            payload = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
            return KisToken(**payload)
        except (OSError, TypeError, ValueError):
            return None

    def _save_cached_token(self, token: KisToken) -> None:
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_cache_path.write_text(json.dumps(asdict(token), ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_expires_at(payload: dict[str, Any]) -> datetime:
    explicit_expiry = payload.get("access_token_token_expired")
    if isinstance(explicit_expiry, str) and explicit_expiry:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"):
            try:
                return datetime.strptime(explicit_expiry, fmt).replace(tzinfo=KST).astimezone(timezone.utc)
            except ValueError:
                pass

    expires_in = int(payload.get("expires_in") or 24 * 60 * 60)
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in)


def _resolve_token_cache_path(token_cache_path: str, env: str) -> Path:
    path = Path(token_cache_path)
    if path.name == "kis_token.json":
        return path.with_name(f"kis_token_{env}.json")
    return path
