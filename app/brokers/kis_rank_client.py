from typing import Any
import time
from dataclasses import replace

from app.brokers.kis_client import KisClient
from app.brokers.rate_limiter import RateLimiter
from app.disclosures.dart_client import DartClient
from app.disclosures.sec_client import SecClient
from app.models import MarketSnapshot


class KisRankClient:
    def __init__(
        self,
        kis_client: KisClient,
        request_interval_seconds: float,
        rank_count: int,
        dart_client: DartClient | None = None,
        sec_client: SecClient | None = None,
    ) -> None:
        self.kis_client = kis_client
        self.rate_limiter = RateLimiter(request_interval_seconds)
        self.rank_count = rank_count
        self.dart_client = dart_client
        self.sec_client = sec_client

    async def get_kr_snapshots(self) -> list[MarketSnapshot]:
        ranked_rows = self._load_ranked_rows()
        snapshots: list[MarketSnapshot] = []
        seen: set[str] = set()

        for row in ranked_rows[: self.rank_count]:
            symbol = row["symbol"]
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)

            name = row["name"] or symbol
            self.rate_limiter.wait()
            try:
                snapshot = self._get_domestic_price_with_retry(symbol, name)
                disclosure_risk = self._risk_score(symbol)
                snapshots.append(
                    replace(
                        snapshot,
                        volume_ratio=row["volume_ratio_proxy"],
                        disclosure_risk=disclosure_risk,
                    )
                )
            except Exception as exc:
                print(f"KR ranked quote failed {symbol}: {exc}")
        return snapshots

    def _load_ranked_rows(self) -> list[dict[str, Any]]:
        rows_by_symbol: dict[str, dict[str, Any]] = {}

        self.rate_limiter.wait()
        self._merge_rank_rows(
            rows_by_symbol,
            _extract_rows(self.kis_client.get_domestic_fluctuation_rank_raw(count=self.rank_count)),
            source="fluctuation",
            volume_ratio_proxy=2.5,
        )

        self.rate_limiter.wait()
        self._merge_rank_rows(
            rows_by_symbol,
            _extract_rows(self.kis_client.get_domestic_volume_rank_raw(rank_type="1")),
            source="volume_increase",
            volume_ratio_proxy=4.0,
        )

        self.rate_limiter.wait()
        self._merge_rank_rows(
            rows_by_symbol,
            _extract_rows(self.kis_client.get_domestic_volume_rank_raw(rank_type="3")),
            source="trading_value",
            volume_ratio_proxy=3.0,
        )

        return sorted(rows_by_symbol.values(), key=lambda row: row["source_score"], reverse=True)

    def _merge_rank_rows(
        self,
        rows_by_symbol: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
        source: str,
        volume_ratio_proxy: float,
    ) -> None:
        for idx, row in enumerate(rows[: self.rank_count], start=1):
            symbol = _first_text(row, ["stck_shrn_iscd", "mksc_shrn_iscd", "iscd", "pdno"])
            if not symbol:
                continue
            name = _first_text(row, ["hts_kor_isnm", "data_rank_name", "prdt_name", "name"]) or symbol
            current = rows_by_symbol.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "name": name,
                    "sources": set(),
                    "source_score": 0,
                    "volume_ratio_proxy": 1.0,
                },
            )
            current["name"] = current["name"] or name
            current["sources"].add(source)
            current["source_score"] += max(1, self.rank_count - idx + 1)
            current["volume_ratio_proxy"] = max(current["volume_ratio_proxy"], volume_ratio_proxy)

    async def get_us_snapshots(self) -> list[MarketSnapshot]:
        ranked_rows = self._load_us_ranked_rows()
        snapshots: list[MarketSnapshot] = []
        seen: set[str] = set()

        for row in ranked_rows[: self.rank_count]:
            symbol = row["symbol"]
            exchange = row["exchange"]
            key = f"{exchange}:{symbol}"
            if not symbol or key in seen:
                continue
            seen.add(key)

            self.rate_limiter.wait()
            try:
                snapshot = self.kis_client.get_overseas_price(symbol, exchange=exchange, name=row["name"] or symbol)
                snapshots.append(
                    replace(
                        snapshot,
                        volume_ratio=row["volume_ratio_proxy"],
                        news_score=max(snapshot.news_score, row["news_score_proxy"]),
                        disclosure_risk=self._sec_risk_score(symbol),
                    )
                )
            except Exception as exc:
                print(f"US ranked quote failed {exchange}:{symbol}: {exc}")
        return snapshots

    def _load_us_ranked_rows(self) -> list[dict[str, Any]]:
        rows_by_symbol: dict[str, dict[str, Any]] = {}
        for exchange in ("NAS", "NYS", "AMS"):
            self.rate_limiter.wait()
            self._merge_us_rank_rows(
                rows_by_symbol,
                _extract_rows(self.kis_client.get_overseas_volume_surge_raw(exchange=exchange)),
                source="volume_surge",
                exchange=exchange,
                volume_ratio_proxy=4.0,
                news_score_proxy=0.2,
            )

            self.rate_limiter.wait()
            self._merge_us_rank_rows(
                rows_by_symbol,
                _extract_rows(self.kis_client.get_overseas_volume_power_raw(exchange=exchange)),
                source="volume_power",
                exchange=exchange,
                volume_ratio_proxy=3.0,
                news_score_proxy=0.1,
            )
        return sorted(rows_by_symbol.values(), key=lambda row: row["source_score"], reverse=True)

    def _merge_us_rank_rows(
        self,
        rows_by_symbol: dict[str, dict[str, Any]],
        rows: list[dict[str, Any]],
        source: str,
        exchange: str,
        volume_ratio_proxy: float,
        news_score_proxy: float,
    ) -> None:
        for idx, row in enumerate(rows[: self.rank_count], start=1):
            symbol = _first_text(row, ["symb", "SYMB", "rsym", "ovrs_pdno", "pdno", "symbol"]).upper()
            if not symbol:
                continue
            key = f"{exchange}:{symbol}"
            name = _first_text(row, ["name", "ename", "ovrs_item_name", "prdt_name"]) or symbol
            current = rows_by_symbol.setdefault(
                key,
                {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "sources": set(),
                    "source_score": 0,
                    "volume_ratio_proxy": 1.0,
                    "news_score_proxy": 0.0,
                },
            )
            current["name"] = current["name"] or name
            current["sources"].add(source)
            current["source_score"] += max(1, self.rank_count - idx + 1)
            current["volume_ratio_proxy"] = max(current["volume_ratio_proxy"], volume_ratio_proxy)
            current["news_score_proxy"] = max(current["news_score_proxy"], news_score_proxy)

    def _get_domestic_price_with_retry(self, symbol: str, name: str) -> MarketSnapshot:
        try:
            return self.kis_client.get_domestic_price(symbol, name=name)
        except RuntimeError as exc:
            if "EGW00201" not in str(exc):
                raise
            time.sleep(max(1.2, self.rate_limiter.interval_seconds))
            return self.kis_client.get_domestic_price(symbol, name=name)

    def _risk_score(self, symbol: str) -> float:
        if not self.dart_client:
            return 0.0
        try:
            return self.dart_client.risk_score(symbol)
        except Exception as exc:
            print(f"DART risk check failed {symbol}: {exc}")
            return 0.0

    def _sec_risk_score(self, symbol: str) -> float:
        if not self.sec_client:
            return 0.0
        try:
            return self.sec_client.risk_score(symbol)
        except Exception as exc:
            print(f"SEC risk check failed {symbol}: {exc}")
            return 0.0


def _extract_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("output", "output1", "output2"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    for key in ("output", "output1", "output2"):
        value = payload.get(key)
        if isinstance(value, dict):
            return [value]
    return []


def _first_text(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
