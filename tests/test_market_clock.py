from datetime import datetime
from datetime import timedelta, timezone

from app.market_clock import (
    is_us_market_open,
    is_us_regular_market_open,
)

KST = timezone(timedelta(hours=9))


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
