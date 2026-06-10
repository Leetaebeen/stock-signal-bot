from datetime import date, timedelta
from typing import Any

import httpx

COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

FALLBACK_TICKER_CIK = {
    "AAPL": "0000320193",
    "AMD": "0000002488",
    "AMZN": "0001018724",
    "AVGO": "0001730168",
    "GOOG": "0001652044",
    "GOOGL": "0001652044",
    "META": "0001326801",
    "MSFT": "0000789019",
    "NFLX": "0001065280",
    "NVDA": "0001045810",
    "PLTR": "0001321655",
    "TSLA": "0001318605",
}

HIGH_RISK_FORMS = {"S-1", "S-1/A", "F-1", "F-1/A", "S-3", "S-3/A", "424B5", "424B3", "EFFECT"}
MEDIUM_RISK_FORMS = {"8-K", "6-K"}


class SecClient:
    def __init__(self, user_agent: str, http_client: httpx.Client | None = None) -> None:
        self.user_agent = user_agent
        self.http_client = http_client or httpx.Client(timeout=10)
        self._ticker_to_cik: dict[str, str] | None = None
        self.last_status = "not_checked"

    @property
    def enabled(self) -> bool:
        return bool(
            self.user_agent
            and "example.com" not in self.user_agent
            and "domain.com" not in self.user_agent
            and "@" in self.user_agent
        )

    def recent_filings(self, ticker: str, days: int = 14, limit: int = 20) -> list[dict[str, Any]]:
        if not self.enabled:
            self.last_status = "disabled"
            return []

        cik = self.lookup_cik(ticker)
        if not cik:
            if self.last_status == "not_checked":
                self.last_status = "cik_not_found"
            return []

        response = self.http_client.get(
            SUBMISSIONS_URL.format(cik=cik),
            headers=self._headers(),
        )
        if response.status_code == 403:
            self.last_status = "blocked_403"
            return []
        response.raise_for_status()
        recent = response.json().get("filings", {}).get("recent", {})
        filings = _recent_columns_to_rows(recent)
        cutoff = date.today() - timedelta(days=days)
        self.last_status = "ok"
        filtered = []
        for filing in filings[:limit]:
            filing_date = _parse_date(filing.get("filingDate"))
            if filing_date and filing_date >= cutoff:
                filtered.append(filing)
        return filtered

    def risk_score(self, ticker: str, days: int = 14) -> float:
        filings = self.recent_filings(ticker, days=days)
        return evaluate_sec_risk(filings)

    def lookup_cik(self, ticker: str) -> str:
        fallback = FALLBACK_TICKER_CIK.get(ticker.upper())
        if fallback:
            return fallback
        ticker_map = self._load_ticker_map()
        return ticker_map.get(ticker.upper(), "")

    def _load_ticker_map(self) -> dict[str, str]:
        if self._ticker_to_cik is not None:
            return self._ticker_to_cik
        if not self.enabled:
            self._ticker_to_cik = {}
            self.last_status = "disabled"
            return self._ticker_to_cik

        response = self.http_client.get(COMPANY_TICKERS_URL, headers=self._headers())
        if response.status_code == 403:
            self._ticker_to_cik = {}
            self.last_status = "blocked_403"
            return self._ticker_to_cik
        response.raise_for_status()
        payload = response.json()
        self._ticker_to_cik = {
            str(item["ticker"]).upper(): str(item["cik_str"]).zfill(10)
            for item in payload.values()
            if isinstance(item, dict) and item.get("ticker") and item.get("cik_str") is not None
        }
        return self._ticker_to_cik

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
        }


def evaluate_sec_risk(filings: list[dict[str, Any]]) -> float:
    risk = 0.0
    for filing in filings:
        form = str(filing.get("form") or "").upper()
        description = str(filing.get("primaryDocDescription") or "")
        if form in HIGH_RISK_FORMS:
            risk += 8.0
        elif form in MEDIUM_RISK_FORMS and _contains_medium_risk_text(description):
            risk += 4.0
    return min(10.0, risk)


def _recent_columns_to_rows(recent: dict[str, list[Any]]) -> list[dict[str, Any]]:
    if not recent:
        return []
    keys = list(recent.keys())
    row_count = max((len(value) for value in recent.values() if isinstance(value, list)), default=0)
    rows = []
    for idx in range(row_count):
        rows.append({key: recent.get(key, [None] * row_count)[idx] for key in keys})
    return rows


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _contains_medium_risk_text(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in ("offering", "delisting", "bankruptcy", "litigation", "warrant"))
