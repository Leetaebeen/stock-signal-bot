from decimal import Decimal, ROUND_HALF_UP

from app.models import SignalCandidate


USD_KRW_RATE = 1350.0


def build_scan_start_message(market_name: str) -> str:
    return (
        f"[{market_name} 감시 시작]\n"
        "급등주 포착 알림을 시작합니다.\n"
        "자동주문은 실행하지 않습니다."
    )


def build_signal_message(candidate: SignalCandidate) -> str:
    snap = candidate.snapshot
    return (
        "[급등주 포착 알림]\n"
        "------------------------------\n"
        f"종목명: {snap.name} ({snap.symbol})\n"
        f"현재가: {_format_snapshot_price(snap)}\n"
        f"상승률: {snap.change_pct:+.2f}%\n"
        f"거래량: {snap.volume_ratio:.2f}배\n"
        "자동주문은 실행하지 않습니다."
    )


def _format_snapshot_price(snapshot) -> str:
    if snapshot.price <= 0:
        return "가격 확인 실패"
    price_krw = snapshot.price_krw if snapshot.price_krw and snapshot.price_krw > 0 else snapshot.price * USD_KRW_RATE
    return f"{_round_won(price_krw):,}원"


def _round_won(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
