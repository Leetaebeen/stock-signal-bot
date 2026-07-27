from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
import time
from typing import Protocol

from app.trading.strategy import KST


logger = logging.getLogger(__name__)


class HolidayClient(Protocol):
    def is_market_business_day(self, market: str, date_value: datetime) -> bool | None:
        ...


@dataclass(frozen=True)
class CalendarResult:
    is_open: bool
    source: str
    market_date: date


class MarketCalendar:
    def __init__(
        self,
        client: HolidayClient,
        *,
        enabled: bool = True,
        cache_seconds: int = 21600,
    ) -> None:
        self.client = client
        self.enabled = enabled
        self.cache_seconds = max(cache_seconds, 300)
        self._cache: dict[tuple[str, date], tuple[float, CalendarResult]] = {}

    def check(self, market: str, now: datetime | None = None) -> CalendarResult:
        normalized_market = market.strip().upper()
        current = (now or datetime.now(KST)).astimezone(KST)
        market_date = _market_date(normalized_market, current)
        if market_date.weekday() >= 5:
            return CalendarResult(False, "weekend", market_date)
        if not self.enabled:
            return CalendarResult(True, "disabled", market_date)

        key = (normalized_market, market_date)
        monotonic_now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached[0] > monotonic_now:
            return cached[1]

        if str(getattr(self.client, "env", "")).lower() == "paper":
            result = _local_calendar_result(normalized_market, market_date)
        else:
            try:
                api_value = self.client.is_market_business_day(
                    normalized_market,
                    datetime.combine(market_date, datetime.min.time(), tzinfo=KST),
                )
                result = (
                    CalendarResult(api_value, "kis", market_date)
                    if api_value is not None
                    else _local_calendar_result(normalized_market, market_date)
                )
            except Exception as exc:
                logger.warning(
                    "holiday lookup fallback market=%s date=%s reason=%s",
                    normalized_market,
                    market_date,
                    exc,
                )
                result = _local_calendar_result(normalized_market, market_date)

        self._cache[key] = (monotonic_now + self.cache_seconds, result)
        return result


def _market_date(market: str, current_kst: datetime) -> date:
    if market == "US" and current_kst.hour <= 6:
        return (current_kst - timedelta(days=1)).date()
    return current_kst.date()


def _local_calendar_result(market: str, market_date: date) -> CalendarResult:
    try:
        import holidays

        if market == "US":
            calendar = holidays.financial_holidays("XNYS", years=market_date.year)
        else:
            calendar = holidays.country_holidays("KR", years=market_date.year)
        return CalendarResult(market_date not in calendar, "local_holidays", market_date)
    except (ImportError, KeyError, ValueError):
        return CalendarResult(True, "weekday_fallback", market_date)
