from datetime import datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9))
KR_REGULAR_OPEN = time(9, 0)
KR_REGULAR_CLOSE = time(15, 30)
US_EXTENDED_OPEN = time(17, 0)
US_REGULAR_OPEN = time(22, 30)
US_REGULAR_CLOSE = time(5, 0)
US_EXTENDED_CLOSE = time(9, 0)


def now_kst() -> datetime:
    return datetime.now(KST)


def is_kr_regular_market_open(moment: datetime | None = None) -> bool:
    current = moment.astimezone(KST) if moment else now_kst()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    return KR_REGULAR_OPEN <= current_time <= KR_REGULAR_CLOSE


def is_us_market_open(moment: datetime | None = None) -> bool:
    current = moment.astimezone(KST) if moment else now_kst()
    current_time = current.time()

    if current.weekday() <= 4 and current_time >= US_EXTENDED_OPEN:
        return True
    if 1 <= current.weekday() <= 5 and current_time <= US_EXTENDED_CLOSE:
        return True
    return False


def is_us_regular_market_open(moment: datetime | None = None) -> bool:
    current = moment.astimezone(KST) if moment else now_kst()
    current_time = current.time()

    if current.weekday() <= 4 and current_time >= US_REGULAR_OPEN:
        return True
    if 1 <= current.weekday() <= 5 and current_time <= US_REGULAR_CLOSE:
        return True
    return False


def seconds_until_next_kr_regular_open(moment: datetime | None = None) -> int:
    current = moment.astimezone(KST) if moment else now_kst()
    next_open = current.replace(hour=9, minute=0, second=0, microsecond=0)
    if current.time() >= KR_REGULAR_OPEN or current.weekday() >= 5:
        next_open = next_open + timedelta(days=1 if current.time() >= KR_REGULAR_OPEN else 0)
    while next_open.weekday() >= 5:
        next_open = next_open + timedelta(days=1)

    return max(1, int((next_open - current).total_seconds()))
