from datetime import datetime
from datetime import timedelta, timezone

from app.market_clock import (
    is_kr_regular_market_open,
    is_us_market_open,
    is_us_regular_market_open,
    seconds_until_next_kr_regular_open,
)

KST = timezone(timedelta(hours=9))


def test_kr_regular_market_open_during_weekday_session():
    moment = datetime(2026, 6, 10, 10, 0, tzinfo=KST)

    assert is_kr_regular_market_open(moment)


def test_kr_regular_market_closed_after_session():
    moment = datetime(2026, 6, 10, 21, 15, tzinfo=KST)

    assert not is_kr_regular_market_open(moment)


def test_kr_regular_market_closed_on_weekend():
    moment = datetime(2026, 6, 13, 10, 0, tzinfo=KST)

    assert not is_kr_regular_market_open(moment)


def test_seconds_until_next_open_before_market():
    moment = datetime(2026, 6, 10, 8, 59, tzinfo=KST)

    assert seconds_until_next_kr_regular_open(moment) == 60


def test_us_market_open_on_kst_monday_evening():
    moment = datetime(2026, 6, 15, 21, 0, tzinfo=KST)

    assert is_us_market_open(moment)
    assert not is_us_regular_market_open(moment)


def test_us_regular_market_open_on_kst_tuesday_early_morning():
    moment = datetime(2026, 6, 16, 3, 0, tzinfo=KST)

    assert is_us_market_open(moment)
    assert is_us_regular_market_open(moment)


def test_us_market_closed_on_kst_monday_morning():
    moment = datetime(2026, 6, 15, 8, 0, tzinfo=KST)

    assert not is_us_market_open(moment)


def test_us_market_open_on_kst_saturday_early_morning():
    moment = datetime(2026, 6, 13, 4, 0, tzinfo=KST)

    assert is_us_market_open(moment)
    assert is_us_regular_market_open(moment)
