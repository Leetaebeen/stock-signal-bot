from datetime import datetime

from app.trading.sessions import KST, SessionPolicy, US_EASTERN_DAYLIGHT, is_kr_regular_open, is_us_extended_open, is_us_regular_open


def test_kr_regular_session_open_and_closed():
    assert is_kr_regular_open(datetime(2026, 7, 7, 10, 0, tzinfo=KST))
    assert not is_kr_regular_open(datetime(2026, 7, 7, 16, 0, tzinfo=KST))


def test_us_regular_session_uses_eastern_time():
    assert is_us_regular_open(datetime(2026, 7, 6, 10, 0, tzinfo=US_EASTERN_DAYLIGHT))
    assert not is_us_regular_open(datetime(2026, 7, 6, 8, 0, tzinfo=US_EASTERN_DAYLIGHT))


def test_us_extended_sessions():
    assert is_us_extended_open(datetime(2026, 7, 6, 8, 0, tzinfo=US_EASTERN_DAYLIGHT), "pre")
    assert is_us_extended_open(datetime(2026, 7, 6, 18, 0, tzinfo=US_EASTERN_DAYLIGHT), "after")
    assert not is_us_extended_open(datetime(2026, 7, 4, 10, 0, tzinfo=US_EASTERN_DAYLIGHT), "day")


def test_session_policy_blocks_extended_by_default():
    policy = SessionPolicy(allow_us_extended=False)

    assert not policy.is_market_open("US", datetime(2026, 7, 6, 8, 0, tzinfo=US_EASTERN_DAYLIGHT), "pre")
