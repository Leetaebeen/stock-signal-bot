from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone


KST = timezone(timedelta(hours=9), name="KST")
US_EASTERN_STANDARD = timezone(timedelta(hours=-5), name="EST")
US_EASTERN_DAYLIGHT = timezone(timedelta(hours=-4), name="EDT")


@dataclass(frozen=True)
class SessionPolicy:
    allow_kr_regular: bool = True
    allow_us_regular: bool = True
    allow_us_extended: bool = False

    def is_market_open(self, market: str, now: datetime | None = None, session: str = "regular") -> bool:
        normalized_market = market.strip().upper()
        normalized_session = session.strip().lower()
        current = now or datetime.now(KST)
        if normalized_market == "KR":
            return self.allow_kr_regular and is_kr_regular_open(current)
        if normalized_market == "US":
            if normalized_session == "regular":
                return self.allow_us_regular and is_us_regular_open(current)
            return self.allow_us_extended and is_us_extended_open(current, normalized_session)
        return False


def is_kr_regular_open(now: datetime | None = None) -> bool:
    current = _as_kst(now or datetime.now(KST))
    if current.weekday() >= 5:
        return False
    return time(9, 0) <= current.time() <= time(15, 30)


def is_us_regular_open(now: datetime | None = None) -> bool:
    current = _as_us_eastern(now or datetime.now(KST))
    if current.weekday() >= 5:
        return False
    return time(9, 30) <= current.time() <= time(16, 0)


def is_us_extended_open(now: datetime | None = None, session: str = "regular") -> bool:
    current = _as_us_eastern(now or datetime.now(KST))
    if current.weekday() >= 5:
        return False
    normalized = session.strip().lower()
    if normalized in {"pre", "premarket", "pre-market"}:
        return time(4, 0) <= current.time() < time(9, 30)
    if normalized in {"after", "aftermarket", "after-market"}:
        return time(16, 0) < current.time() <= time(20, 0)
    if normalized in {"day", "daytime", "day-market"}:
        return True
    return is_us_regular_open(current)


def market_closed_reason(market: str, now: datetime | None = None, session: str = "regular") -> str:
    normalized_market = market.strip().upper()
    if normalized_market == "KR":
        return "국장 정규장 시간이 아님"
    if normalized_market == "US":
        if session == "regular":
            return "미장 정규장 시간이 아님"
        return f"미장 {session} 세션이 비활성화되었거나 시간이 아님"
    return "지원하지 않는 시장"


def _as_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _as_us_eastern(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=KST)
    utc_value = value.astimezone(timezone.utc)
    eastern = utc_value.astimezone(US_EASTERN_DAYLIGHT if _is_us_dst_utc(utc_value) else US_EASTERN_STANDARD)
    return eastern


def _is_us_dst_utc(value: datetime) -> bool:
    year = value.year
    dst_start_local = datetime.combine(_nth_weekday(year, 3, 6, 2), time(2, 0), tzinfo=US_EASTERN_STANDARD)
    dst_end_local = datetime.combine(_nth_weekday(year, 11, 6, 1), time(2, 0), tzinfo=US_EASTERN_DAYLIGHT)
    return dst_start_local.astimezone(timezone.utc) <= value < dst_end_local.astimezone(timezone.utc)


def _nth_weekday(year: int, month: int, weekday: int, nth: int):
    current = datetime(year, month, 1)
    days_until = (weekday - current.weekday()) % 7
    return (current + timedelta(days=days_until + (nth - 1) * 7)).date()
