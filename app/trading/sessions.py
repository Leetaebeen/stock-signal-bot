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


def active_markets(policy: SessionPolicy, now: datetime | None = None, us_session: str = "regular") -> list[str]:
    current = now or datetime.now(KST)
    markets = []
    if policy.is_market_open("KR", now=current, session="regular"):
        markets.append("KR")
    if policy.is_market_open("US", now=current, session=us_session):
        markets.append("US")
    return markets


def is_kr_regular_open(now: datetime | None = None) -> bool:
    current = _as_kst(now or datetime.now(KST))
    if current.weekday() >= 5:
        return False
    return time(8, 0) <= current.time() <= time(16, 0)


def is_us_regular_open(now: datetime | None = None) -> bool:
    current = _as_kst(now or datetime.now(KST))
    current_time = current.time()
    if current_time >= time(22, 30):
        return current.weekday() <= 4
    if current_time <= time(5, 0):
        return 1 <= current.weekday() <= 5
    return False


def is_us_extended_open(now: datetime | None = None, session: str = "regular") -> bool:
    return False


def market_closed_reason(market: str, now: datetime | None = None, session: str = "regular") -> str:
    normalized_market = market.strip().upper()
    if normalized_market == "KR":
        return "국장 거래 시간이 아님"
    if normalized_market == "US":
        return "미장 거래 시간이 아님"
    return "지원하지 않는 시장"


def _as_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)
