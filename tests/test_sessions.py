from datetime import datetime

from app.trading.sessions import KST, SessionPolicy, is_kr_regular_open, is_us_extended_open, is_us_regular_open


def test_kr_regular_session_uses_kst_window():
    assert is_kr_regular_open(datetime(2026, 7, 13, 8, 0, tzinfo=KST))
    assert is_kr_regular_open(datetime(2026, 7, 13, 15, 59, tzinfo=KST))
    assert is_kr_regular_open(datetime(2026, 7, 13, 16, 0, tzinfo=KST))
    assert not is_kr_regular_open(datetime(2026, 7, 13, 7, 59, tzinfo=KST))
    assert not is_kr_regular_open(datetime(2026, 7, 13, 16, 1, tzinfo=KST))


def test_kr_regular_session_blocks_weekends():
    assert not is_kr_regular_open(datetime(2026, 7, 11, 10, 0, tzinfo=KST))


def test_us_regular_session_uses_kst_night_window():
    assert is_us_regular_open(datetime(2026, 7, 13, 22, 30, tzinfo=KST))
    assert is_us_regular_open(datetime(2026, 7, 14, 2, 0, tzinfo=KST))
    assert is_us_regular_open(datetime(2026, 7, 14, 5, 0, tzinfo=KST))
    assert not is_us_regular_open(datetime(2026, 7, 13, 22, 29, tzinfo=KST))
    assert not is_us_regular_open(datetime(2026, 7, 14, 5, 1, tzinfo=KST))


def test_us_regular_session_blocks_sunday_night_and_monday_dawn_kst():
    assert not is_us_regular_open(datetime(2026, 7, 12, 23, 0, tzinfo=KST))
    assert not is_us_regular_open(datetime(2026, 7, 13, 2, 0, tzinfo=KST))


def test_us_extended_sessions_disabled():
    assert not is_us_extended_open(datetime(2026, 7, 13, 21, 0, tzinfo=KST), "pre")


def test_session_policy_uses_kst_windows():
    policy = SessionPolicy()

    assert policy.is_market_open("KR", datetime(2026, 7, 13, 9, 0, tzinfo=KST), "regular")
    assert not policy.is_market_open("US", datetime(2026, 7, 13, 9, 0, tzinfo=KST), "regular")
    assert policy.is_market_open("US", datetime(2026, 7, 13, 23, 0, tzinfo=KST), "regular")
    assert not policy.is_market_open("KR", datetime(2026, 7, 13, 23, 0, tzinfo=KST), "regular")
