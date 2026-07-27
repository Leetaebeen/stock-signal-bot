from dataclasses import dataclass
import logging
import time
from typing import Protocol

from app.brokers.kis_client import RankedSymbol


logger = logging.getLogger(__name__)


class RankingClient(Protocol):
    def get_domestic_ranked_symbols(self, limit: int = 20) -> list[RankedSymbol]:
        ...

    def get_overseas_ranked_symbols(
        self,
        exchange: str = "NAS",
        limit: int = 10,
    ) -> list[RankedSymbol]:
        ...


@dataclass(frozen=True)
class UniverseSelection:
    symbols: list[str]
    exchange_by_symbol: dict[str, str]
    name_by_symbol: dict[str, str]
    source: str


class DynamicUniverseProvider:
    def __init__(
        self,
        client: RankingClient,
        *,
        enabled: bool = True,
        refresh_seconds: int = 300,
        kr_limit: int = 20,
        us_limit_per_exchange: int = 10,
        us_exchanges: tuple[str, ...] = ("NAS", "NYS", "AMS"),
    ) -> None:
        self.client = client
        self.enabled = enabled
        self.refresh_seconds = max(refresh_seconds, 30)
        self.kr_limit = max(kr_limit, 1)
        self.us_limit_per_exchange = max(us_limit_per_exchange, 1)
        self.us_exchanges = tuple(item.strip().upper() for item in us_exchanges if item.strip())
        self._cache: dict[str, tuple[float, UniverseSelection]] = {}

    def select_kr(self, fallback: list[str]) -> UniverseSelection:
        return self._select("KR", fallback, {})

    def select_us(
        self,
        fallback: list[str],
        fallback_exchanges: dict[str, str],
    ) -> UniverseSelection:
        return self._select("US", fallback, fallback_exchanges)

    def _select(
        self,
        market: str,
        fallback: list[str],
        fallback_exchanges: dict[str, str],
    ) -> UniverseSelection:
        if not self.enabled:
            return UniverseSelection(
                _dedupe(fallback),
                dict(fallback_exchanges),
                {},
                "configured",
            )

        now = time.monotonic()
        cached = self._cache.get(market)
        if cached and cached[0] > now:
            return cached[1]

        try:
            if market == "KR":
                ranked = self.client.get_domestic_ranked_symbols(limit=self.kr_limit)
            else:
                ranked = []
                for exchange in self.us_exchanges:
                    ranked.extend(
                        self.client.get_overseas_ranked_symbols(
                            exchange=exchange,
                            limit=self.us_limit_per_exchange,
                        )
                    )
            symbols = _dedupe([item.symbol for item in ranked])
            if not symbols:
                raise RuntimeError("ranking API returned no symbols")
            exchanges = {
                item.symbol: item.exchange
                for item in ranked
                if item.exchange
            }
            names = {
                item.symbol: item.name
                for item in ranked
                if item.name
            }
            selection = UniverseSelection(symbols, exchanges, names, "kis_rank")
        except Exception as exc:
            logger.warning("dynamic universe fallback market=%s reason=%s", market, exc)
            selection = UniverseSelection(
                _dedupe(fallback),
                dict(fallback_exchanges),
                {},
                "configured_fallback",
            )

        self._cache[market] = (now + self.refresh_seconds, selection)
        return selection


def parse_exchanges(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(_dedupe(value.replace("\n", ",").split(",")))


def _dedupe(values: list[str]) -> list[str]:
    result = []
    for raw in values:
        value = raw.strip().upper()
        if value and value not in result:
            result.append(value)
    return result
