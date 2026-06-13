from datetime import datetime, time, timedelta, timezone

KST = timezone(timedelta(hours=9))
US_EXTENDED_OPEN = time(17, 0)
US_REGULAR_OPEN = time(22, 30)
US_REGULAR_CLOSE = time(5, 0)
US_EXTENDED_CLOSE = time(9, 0)


def now_kst() -> datetime:
    return datetime.now(KST)


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
