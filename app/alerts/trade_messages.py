from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class TradeFill:
    symbol: str
    name: str
    market: str
    side: str
    quantity: float
    price: float
    reason: str
    currency: str = "USD"
    filled_at: datetime | None = None
    entry_price: float | None = None
    holding_seconds: int | None = None


@dataclass(frozen=True)
class OrderFailure:
    symbol: str
    name: str
    market: str
    side: str
    reason: str
    failed_at: datetime | None = None


def build_trade_fill_message(fill: TradeFill) -> str:
    if fill.side.upper() == "BUY":
        return _build_buy_fill_message(fill)
    if fill.side.upper() == "SELL":
        return _build_sell_fill_message(fill)
    raise ValueError("side must be BUY or SELL")


def build_order_failure_message(failure: OrderFailure) -> str:
    return (
        "[모의 주문 실패]\n"
        "------------------------------\n"
        f"종목: {failure.name} ({failure.symbol})\n"
        f"시장: {_market_label(failure.market)}\n"
        f"주문: {_side_label(failure.side)}\n"
        f"사유: {failure.reason}\n"
        f"시간: {_format_time(failure.failed_at)}"
    )


def _build_buy_fill_message(fill: TradeFill) -> str:
    amount = fill.price * fill.quantity
    return (
        "[모의 매수 체결]\n"
        "------------------------------\n"
        f"종목: {fill.name} ({fill.symbol})\n"
        f"시장: {_market_label(fill.market)}\n"
        f"매수가: {_format_price(fill.price, fill.currency)}\n"
        f"수량: {_format_quantity(fill.quantity)}주\n"
        f"주문금액: {_format_price(amount, fill.currency)}\n"
        f"진입 사유: {fill.reason}\n"
        f"시간: {_format_time(fill.filled_at)}"
    )


def _build_sell_fill_message(fill: TradeFill) -> str:
    if fill.entry_price and fill.entry_price > 0:
        pnl = (fill.price - fill.entry_price) * fill.quantity
        pnl_pct = ((fill.price - fill.entry_price) / fill.entry_price) * 100
    else:
        pnl = 0.0
        pnl_pct = 0.0
    return (
        "[모의 매도 체결]\n"
        "------------------------------\n"
        f"종목: {fill.name} ({fill.symbol})\n"
        f"시장: {_market_label(fill.market)}\n"
        f"매수가: {_format_price(fill.entry_price or 0, fill.currency)}\n"
        f"매도가: {_format_price(fill.price, fill.currency)}\n"
        f"수량: {_format_quantity(fill.quantity)}주\n"
        f"수익률: {pnl_pct:+.2f}%\n"
        f"손익: {_format_signed_price(pnl, fill.currency)}\n"
        f"매도 사유: {fill.reason}\n"
        f"보유 시간: {_format_duration(fill.holding_seconds)}\n"
        f"시간: {_format_time(fill.filled_at)}"
    )


def _market_label(market: str) -> str:
    return "국장" if market.upper() == "KR" else "미장"


def _side_label(side: str) -> str:
    return "매수" if side.upper() == "BUY" else "매도"


def _format_price(value: float, currency: str) -> str:
    if currency.upper() == "KRW":
        return f"{value:,.0f}원"
    return f"${value:,.2f}"


def _format_signed_price(value: float, currency: str) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{_format_price(abs(value), currency)}"


def _format_quantity(value: float) -> str:
    return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.4f}".rstrip("0").rstrip(".")


def _format_duration(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return "확인 불가"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}시간 {minutes}분 {sec}초"
    if minutes:
        return f"{minutes}분 {sec}초"
    return f"{sec}초"


def _format_time(value: datetime | None) -> str:
    current = value.astimezone(KST) if value else datetime.now(KST)
    return current.strftime("%Y-%m-%d %H:%M:%S KST")
