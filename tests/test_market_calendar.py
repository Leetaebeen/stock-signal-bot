from datetime import datetime

from app.trading.calendar import MarketCalendar
from app.trading.strategy import KST


class FakeHolidayClient:
    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.dates = []

    def is_market_business_day(self, market, date_value):
        self.calls += 1
        self.dates.append((market, date_value.date()))
        return self.result


def test_market_calendar_blocks_holiday_and_caches_result():
    client = FakeHolidayClient(False)
    calendar = MarketCalendar(client)
    now = datetime(2026, 7, 27, 9, 0, tzinfo=KST)

    first = calendar.check("KR", now)
    second = calendar.check("KR", now)

    assert not first.is_open
    assert first.source == "kis"
    assert second == first
    assert client.calls == 1


def test_market_calendar_uses_previous_date_for_us_dawn():
    client = FakeHolidayClient(True)
    calendar = MarketCalendar(client)

    result = calendar.check("US", datetime(2026, 7, 28, 2, 0, tzinfo=KST))

    assert result.is_open
    assert str(result.market_date) == "2026-07-27"
    assert str(client.dates[0][1]) == "2026-07-27"


def test_market_calendar_blocks_weekend_without_api_call():
    client = FakeHolidayClient(True)
    calendar = MarketCalendar(client)

    result = calendar.check("KR", datetime(2026, 7, 25, 9, 0, tzinfo=KST))

    assert not result.is_open
    assert result.source == "weekend"
    assert client.calls == 0


def test_market_calendar_falls_back_to_weekday_on_api_error():
    class BrokenClient:
        def is_market_business_day(self, market, date_value):
            raise RuntimeError("unsupported")

    result = MarketCalendar(BrokenClient()).check(
        "US",
        datetime(2026, 7, 27, 23, 0, tzinfo=KST),
    )

    assert result.is_open
    assert result.source in {"local_holidays", "weekday_fallback"}


def test_local_calendars_block_known_kr_and_us_holidays():
    class BrokenClient:
        def is_market_business_day(self, market, date_value):
            raise RuntimeError("paper API unsupported")

    calendar = MarketCalendar(BrokenClient())

    kr = calendar.check("KR", datetime(2026, 1, 1, 9, 0, tzinfo=KST))
    us = calendar.check("US", datetime(2026, 7, 3, 23, 0, tzinfo=KST))

    assert not kr.is_open
    assert kr.source == "local_holidays"
    assert not us.is_open
    assert us.source == "local_holidays"


def test_paper_environment_skips_unsupported_holiday_api():
    class PaperClient:
        env = "paper"

        def is_market_business_day(self, market, date_value):
            raise AssertionError("paper holiday API must not be called")

    result = MarketCalendar(PaperClient()).check(
        "KR",
        datetime(2026, 7, 27, 9, 0, tzinfo=KST),
    )

    assert result.is_open
    assert result.source == "local_holidays"
