from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Literal


Action = Literal["BUY", "SELL", "HOLD"]
KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class StrategyRules:
    entry_min_change_pct: float = 3.0
    entry_max_change_pct: float = 30.0
    entry_min_volume_ratio: float = 4.0
    entry_max_volume_ratio: float = 20.0
    entry_min_trading_value_krw: float = 1_000_000_000
    take_profit_pct: float = 5.0
    stop_loss_pct: float = -2.0
    trailing_start_pct: float = 3.0
    trailing_drawdown_pct: float = 1.5
    max_hold_seconds: int = 30 * 60


@dataclass(frozen=True)
class MarketSignal:
    symbol: str
    name: str
    market: str
    price: float
    change_pct: float
    volume_ratio: float
    trading_value_krw: float
    observed_at: datetime | None = None


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str
    market: str
    quantity: float
    entry_price: float
    entry_at: datetime
    highest_price: float

    def with_price(self, price: float) -> "Position":
        return replace(self, highest_price=max(self.highest_price, price))


@dataclass(frozen=True)
class TradeDecision:
    action: Action
    reason: str
    score: int = 0

    @property
    def should_buy(self) -> bool:
        return self.action == "BUY"

    @property
    def should_sell(self) -> bool:
        return self.action == "SELL"


def evaluate_entry(signal: MarketSignal, rules: StrategyRules) -> TradeDecision:
    if signal.price <= 0:
        return TradeDecision("HOLD", "현재가가 0 이하라 진입하지 않음")
    if signal.change_pct < rules.entry_min_change_pct:
        return TradeDecision("HOLD", f"등락률 {signal.change_pct:.2f}%가 기준 미달")
    if signal.change_pct > rules.entry_max_change_pct:
        return TradeDecision("HOLD", f"등락률 {signal.change_pct:.2f}%가 과열 기준 초과")
    if signal.volume_ratio < rules.entry_min_volume_ratio:
        return TradeDecision("HOLD", f"거래량 배율 {signal.volume_ratio:.2f}배가 기준 미달")
    if signal.volume_ratio > rules.entry_max_volume_ratio:
        return TradeDecision("HOLD", f"거래량 배율 {signal.volume_ratio:.2f}배가 과열 기준 초과")
    if signal.trading_value_krw < rules.entry_min_trading_value_krw:
        return TradeDecision("HOLD", f"거래대금 {signal.trading_value_krw:,.0f}원이 기준 미달")

    score = _entry_score(signal, rules)
    return TradeDecision(
        "BUY",
        (
            f"급등 초입 조건 통과: 등락률 {signal.change_pct:.2f}%, "
            f"거래량 {signal.volume_ratio:.2f}배, 거래대금 {signal.trading_value_krw:,.0f}원"
        ),
        score=score,
    )


def evaluate_exit(
    position: Position,
    *,
    current_price: float,
    now: datetime | None = None,
    rules: StrategyRules,
) -> TradeDecision:
    if current_price <= 0:
        return TradeDecision("HOLD", "현재가가 0 이하라 매도 판단 보류")
    if position.entry_price <= 0:
        return TradeDecision("SELL", "진입가 오류로 포지션 정리")

    current_time = now or datetime.now(KST)
    pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
    if pnl_pct >= rules.take_profit_pct:
        return TradeDecision("SELL", f"익절 기준 도달: 수익률 {pnl_pct:+.2f}%")
    if pnl_pct <= rules.stop_loss_pct:
        return TradeDecision("SELL", f"손절 기준 도달: 수익률 {pnl_pct:+.2f}%")

    high_pnl_pct = ((position.highest_price - position.entry_price) / position.entry_price) * 100
    drawdown_pct = ((position.highest_price - current_price) / position.highest_price) * 100
    if high_pnl_pct >= rules.trailing_start_pct and drawdown_pct >= rules.trailing_drawdown_pct:
        return TradeDecision(
            "SELL",
            f"상승 후 트레일링: 고점 대비 -{drawdown_pct:.2f}%, 현재 수익률 {pnl_pct:+.2f}%",
        )

    holding_seconds = int((current_time - position.entry_at).total_seconds())
    if holding_seconds >= rules.max_hold_seconds:
        return TradeDecision("SELL", f"최대 보유 시간 초과: {holding_seconds}초")

    return TradeDecision("HOLD", f"보유 유지: 수익률 {pnl_pct:+.2f}%")


def open_position(signal: MarketSignal, quantity: float, entry_at: datetime | None = None) -> Position:
    if quantity <= 0:
        raise ValueError("quantity must be greater than zero.")
    if signal.price <= 0:
        raise ValueError("signal price must be greater than zero.")
    return Position(
        symbol=signal.symbol,
        name=signal.name,
        market=signal.market,
        quantity=quantity,
        entry_price=signal.price,
        entry_at=entry_at or signal.observed_at or datetime.now(KST),
        highest_price=signal.price,
    )


def _entry_score(signal: MarketSignal, rules: StrategyRules) -> int:
    change_span = max(rules.entry_max_change_pct - rules.entry_min_change_pct, 1)
    volume_span = max(rules.entry_max_volume_ratio - rules.entry_min_volume_ratio, 1)
    change_score = min(max((signal.change_pct - rules.entry_min_change_pct) / change_span, 0), 1) * 40
    volume_score = min(max((signal.volume_ratio - rules.entry_min_volume_ratio) / volume_span, 0), 1) * 40
    value_score = min(signal.trading_value_krw / max(rules.entry_min_trading_value_krw, 1), 3) / 3 * 20
    return round(change_score + volume_score + value_score)
