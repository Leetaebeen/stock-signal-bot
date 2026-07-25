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
    entry_min_score: int = 65
    entry_min_confirmation_bars: int = 8
    entry_min_one_minute_change_pct: float = 0.15
    entry_max_one_minute_change_pct: float = 2.5
    entry_min_five_minute_change_pct: float = 0.5
    entry_max_five_minute_change_pct: float = 5.0
    entry_min_breakout_pct: float = 0.0
    entry_max_vwap_extension_pct: float = 2.5
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
    exchange: str | None = None
    one_minute_change_pct: float = 0.0
    five_minute_change_pct: float = 0.0
    breakout_pct: float = 0.0
    vwap_extension_pct: float = 0.0
    confirmation_bars: int = 0


@dataclass(frozen=True)
class Position:
    symbol: str
    name: str
    market: str
    quantity: float
    entry_price: float
    entry_at: datetime
    highest_price: float
    exchange: str | None = None

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
    if signal.confirmation_bars < rules.entry_min_confirmation_bars:
        return TradeDecision(
            "HOLD",
            f"분봉 확인 {signal.confirmation_bars}개가 기준 {rules.entry_min_confirmation_bars}개 미달",
        )
    if signal.one_minute_change_pct < rules.entry_min_one_minute_change_pct:
        return TradeDecision("HOLD", f"1분 상승률 {signal.one_minute_change_pct:.2f}%가 기준 미달")
    if signal.one_minute_change_pct > rules.entry_max_one_minute_change_pct:
        return TradeDecision("HOLD", f"1분 상승률 {signal.one_minute_change_pct:.2f}%가 추격매수 제한 초과")
    if signal.five_minute_change_pct < rules.entry_min_five_minute_change_pct:
        return TradeDecision("HOLD", f"5분 상승률 {signal.five_minute_change_pct:.2f}%가 기준 미달")
    if signal.five_minute_change_pct > rules.entry_max_five_minute_change_pct:
        return TradeDecision("HOLD", f"5분 상승률 {signal.five_minute_change_pct:.2f}%가 과열 기준 초과")
    if signal.breakout_pct < rules.entry_min_breakout_pct:
        return TradeDecision("HOLD", f"직전 고점 대비 {signal.breakout_pct:+.2f}%로 돌파 확인 실패")
    if signal.vwap_extension_pct < 0:
        return TradeDecision("HOLD", f"현재가가 단기 VWAP 아래 {signal.vwap_extension_pct:.2f}%")
    if signal.vwap_extension_pct > rules.entry_max_vwap_extension_pct:
        return TradeDecision("HOLD", f"VWAP 이격 {signal.vwap_extension_pct:.2f}%가 추격매수 제한 초과")

    score = entry_score(signal, rules)
    if score < rules.entry_min_score:
        return TradeDecision("HOLD", f"전략 점수 {score}점이 진입 기준 {rules.entry_min_score}점 미달", score=score)

    return TradeDecision(
        "BUY",
        (
            f"전략 점수 {score}점 통과: 당일 {signal.change_pct:.2f}%, "
            f"1분 {signal.one_minute_change_pct:.2f}%, 5분 {signal.five_minute_change_pct:.2f}%, "
            f"분봉 거래량 {signal.volume_ratio:.2f}배, 고점 돌파 {signal.breakout_pct:+.2f}%"
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
        exchange=signal.exchange,
    )


def entry_score(signal: MarketSignal, rules: StrategyRules) -> int:
    change_score = _score_change(signal.change_pct, rules) * (15 / 35)
    volume_score = _score_volume(signal.volume_ratio, rules) * (25 / 35)
    value_score = _score_trading_value(signal.trading_value_krw, rules) * (15 / 30)
    one_minute_score = _window_score(
        signal.one_minute_change_pct,
        rules.entry_min_one_minute_change_pct,
        rules.entry_max_one_minute_change_pct,
    ) * 10
    five_minute_score = _window_score(
        signal.five_minute_change_pct,
        rules.entry_min_five_minute_change_pct,
        rules.entry_max_five_minute_change_pct,
    ) * 15
    breakout_score = _scale(signal.breakout_pct, rules.entry_min_breakout_pct, 1.0) * 10
    vwap_score = (1 - _scale(signal.vwap_extension_pct, 1.0, rules.entry_max_vwap_extension_pct)) * 10
    overheat_penalty = _overheat_penalty(signal.change_pct, signal.volume_ratio, rules) * 0.5
    total = (
        change_score
        + volume_score
        + value_score
        + one_minute_score
        + five_minute_score
        + breakout_score
        + vwap_score
        - overheat_penalty
    )
    return round(max(min(total, 100), 0))


def _score_change(change_pct: float, rules: StrategyRules) -> float:
    # Best short-term entries are strong but not fully exhausted.
    sweet_spot = min(max(rules.entry_min_change_pct * 2.5, rules.entry_min_change_pct + 1), rules.entry_max_change_pct)
    if change_pct <= sweet_spot:
        return _scale(change_pct, rules.entry_min_change_pct, sweet_spot) * 35
    return (1 - _scale(change_pct, sweet_spot, rules.entry_max_change_pct) * 0.35) * 35


def _score_volume(volume_ratio: float, rules: StrategyRules) -> float:
    sweet_spot = min(max(rules.entry_min_volume_ratio * 2, rules.entry_min_volume_ratio + 1), rules.entry_max_volume_ratio)
    if volume_ratio <= sweet_spot:
        return _scale(volume_ratio, rules.entry_min_volume_ratio, sweet_spot) * 35
    return (1 - _scale(volume_ratio, sweet_spot, rules.entry_max_volume_ratio) * 0.30) * 35


def _score_trading_value(trading_value_krw: float, rules: StrategyRules) -> float:
    target = max(rules.entry_min_trading_value_krw * 5, rules.entry_min_trading_value_krw)
    return _scale(trading_value_krw, rules.entry_min_trading_value_krw, target) * 30


def _overheat_penalty(change_pct: float, volume_ratio: float, rules: StrategyRules) -> float:
    change_pressure = _scale(change_pct, rules.entry_max_change_pct * 0.75, rules.entry_max_change_pct)
    volume_pressure = _scale(volume_ratio, rules.entry_max_volume_ratio * 0.75, rules.entry_max_volume_ratio)
    return (change_pressure * 12) + (volume_pressure * 8)


def _scale(value: float, floor: float, ceiling: float) -> float:
    if ceiling <= floor:
        return 1.0 if value >= ceiling else 0.0
    return min(max((value - floor) / (ceiling - floor), 0), 1)


def _window_score(value: float, floor: float, ceiling: float) -> float:
    if value < floor or value > ceiling:
        return 0.0
    sweet_spot = floor + ((ceiling - floor) * 0.45)
    if value <= sweet_spot:
        return 0.5 + (_scale(value, floor, sweet_spot) * 0.5)
    return 1 - (_scale(value, sweet_spot, ceiling) * 0.35)
