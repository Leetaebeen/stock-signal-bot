from dataclasses import dataclass, replace
from datetime import datetime
import logging
from math import log10
from pathlib import Path
from statistics import median
import time
from typing import Iterable, Protocol

from app.brokers.kis_client import MinuteBar, PriceSnapshot
from app.trading.strategy import KST, MarketSignal, StrategyRules, entry_score


logger = logging.getLogger(__name__)


class QuoteClient(Protocol):
    def get_domestic_price(self, symbol: str, name: str | None = None) -> PriceSnapshot:
        ...

    def get_overseas_price(self, symbol: str, exchange: str = "NAS", name: str | None = None) -> PriceSnapshot:
        ...

    def get_domestic_minute_bars(self, symbol: str, limit: int = 30) -> list[MinuteBar]:
        ...

    def get_overseas_minute_bars(
        self,
        symbol: str,
        exchange: str = "NAS",
        limit: int = 20,
    ) -> list[MinuteBar]:
        ...


@dataclass(frozen=True)
class ScanCandidate:
    signal: MarketSignal
    source: str
    score: float


@dataclass(frozen=True)
class MinuteMomentum:
    relative_volume: float
    one_minute_change_pct: float
    five_minute_change_pct: float
    breakout_pct: float
    vwap_extension_pct: float
    confirmation_bars: int
    volume_acceleration: float
    pullback_depth_pct: float
    rebreak_pct: float


class MomentumScanner:
    def __init__(
        self,
        *,
        quote_client: QuoteClient,
        rules: StrategyRules | None = None,
        exchange: str = "NAS",
        request_delay_seconds: float = 0.0,
    ) -> None:
        self.quote_client = quote_client
        self.rules = rules or StrategyRules()
        self.exchange = exchange
        self.request_delay_seconds = request_delay_seconds

    def scan_us(
        self,
        symbols: Iterable[str],
        limit: int = 5,
        exchange_by_symbol: dict[str, str] | None = None,
        name_by_symbol: dict[str, str] | None = None,
    ) -> list[ScanCandidate]:
        return self._scan(
            symbols,
            market="US",
            limit=limit,
            exchange_by_symbol=exchange_by_symbol or {},
            name_by_symbol=name_by_symbol or {},
        )

    def scan_kr(self, symbols: Iterable[str], limit: int = 5) -> list[ScanCandidate]:
        return self._scan(
            symbols,
            market="KR",
            limit=limit,
            exchange_by_symbol={},
            name_by_symbol={},
        )

    def _scan(
        self,
        symbols: Iterable[str],
        *,
        market: str,
        limit: int,
        exchange_by_symbol: dict[str, str],
        name_by_symbol: dict[str, str],
    ) -> list[ScanCandidate]:
        preliminary: list[MarketSignal] = []
        observed_at = datetime.now(KST)
        for symbol in _clean_symbols(symbols):
            self._wait()
            try:
                if market == "KR":
                    snapshot = self.quote_client.get_domestic_price(symbol)
                else:
                    exchange = exchange_by_symbol.get(symbol, self.exchange)
                    snapshot = self.quote_client.get_overseas_price(
                        symbol,
                        exchange=exchange,
                        name=name_by_symbol.get(symbol),
                    )
            except Exception as exc:
                logger.warning("quote skipped symbol=%s reason=%s", symbol, exc)
                continue
            signal = MarketSignal(
                symbol=snapshot.symbol,
                name=snapshot.name,
                market=market,
                price=snapshot.price,
                change_pct=snapshot.change_pct,
                volume_ratio=0.0,
                trading_value_krw=snapshot.trading_value_krw,
                observed_at=observed_at,
                exchange=snapshot.exchange,
            )
            if _passes_preliminary_filter(signal, self.rules):
                preliminary.append(signal)

        confirmation_pool = sorted(preliminary, key=_preliminary_score, reverse=True)[: max(limit, 1)]
        candidates: list[ScanCandidate] = []
        for signal in confirmation_pool:
            self._wait()
            try:
                if market == "KR":
                    bars = self.quote_client.get_domestic_minute_bars(signal.symbol, limit=20)
                else:
                    bars = self.quote_client.get_overseas_minute_bars(
                        signal.symbol,
                        exchange=signal.exchange or self.exchange,
                        limit=20,
                    )
            except Exception as exc:
                logger.warning("minute chart skipped symbol=%s reason=%s", signal.symbol, exc)
                continue
            momentum = analyze_minute_momentum(signal.price, bars)
            confirmed = replace(
                signal,
                volume_ratio=momentum.relative_volume,
                one_minute_change_pct=momentum.one_minute_change_pct,
                five_minute_change_pct=momentum.five_minute_change_pct,
                breakout_pct=momentum.breakout_pct,
                vwap_extension_pct=momentum.vwap_extension_pct,
                confirmation_bars=momentum.confirmation_bars,
                volume_acceleration=momentum.volume_acceleration,
                pullback_depth_pct=momentum.pullback_depth_pct,
                rebreak_pct=momentum.rebreak_pct,
            )
            candidates.append(
                ScanCandidate(
                    signal=confirmed,
                    source=f"kis_{market.lower()}_minute_confirmed",
                    score=float(entry_score(confirmed, self.rules)),
                )
            )
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:limit]

    def _wait(self) -> None:
        if self.request_delay_seconds > 0:
            time.sleep(self.request_delay_seconds)


def parse_symbol_list(value: str | None) -> list[str]:
    if not value:
        return []
    return _clean_symbols(value.replace("\n", ",").split(","))


def load_symbols_from_file(path: str | None) -> list[str]:
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        return []
    return parse_symbol_list(file_path.read_text(encoding="utf-8"))


def _clean_symbols(symbols: Iterable[str]) -> list[str]:
    cleaned = []
    for raw in symbols:
        symbol = raw.strip().upper()
        if symbol and symbol not in cleaned:
            cleaned.append(symbol)
    return cleaned


def parse_exchange_map(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    exchanges: dict[str, str] = {}
    for item in value.replace("\n", ",").split(","):
        symbol, separator, exchange = item.strip().partition(":")
        if separator and symbol.strip() and exchange.strip():
            exchanges[symbol.strip().upper()] = exchange.strip().upper()
    return exchanges


def analyze_minute_momentum(current_price: float, bars: list[MinuteBar]) -> MinuteMomentum:
    ordered = sorted((bar for bar in bars if bar.close > 0 and bar.volume >= 0), key=lambda bar: bar.timestamp)
    if ordered:
        latest_session = ordered[-1].timestamp[:8]
        ordered = [bar for bar in ordered if bar.timestamp[:8] == latest_session]
    if len(ordered) < 8 or current_price <= 0:
        return MinuteMomentum(
            relative_volume=0.0,
            one_minute_change_pct=0.0,
            five_minute_change_pct=0.0,
            breakout_pct=0.0,
            vwap_extension_pct=0.0,
            confirmation_bars=len(ordered),
            volume_acceleration=0.0,
            pullback_depth_pct=0.0,
            rebreak_pct=0.0,
        )

    completed = ordered[-2]
    previous = ordered[-3]
    five_minutes_ago = ordered[-7]
    baseline_bars = ordered[max(0, len(ordered) - 12) : -2]
    baseline_volumes = [bar.volume for bar in baseline_bars if bar.volume > 0]
    baseline_volume = median(baseline_volumes) if baseline_volumes else 0.0
    relative_volume = completed.volume / baseline_volume if baseline_volume > 0 else 0.0

    acceleration_bars = ordered[max(0, len(ordered) - 6) : -2]
    acceleration_volumes = [bar.volume for bar in acceleration_bars if bar.volume > 0]
    acceleration_baseline = median(acceleration_volumes) if acceleration_volumes else 0.0
    volume_acceleration = (
        completed.volume / acceleration_baseline if acceleration_baseline > 0 else 0.0
    )

    breakout_window = ordered[-7:-2]
    previous_high = max((bar.high for bar in breakout_window if bar.high > 0), default=0.0)
    breakout_pct = _percent_change(current_price, previous_high) if previous_high > 0 else 0.0

    rebreak_window = ordered[-8:-3]
    rebreak_reference = max((bar.high for bar in rebreak_window if bar.high > 0), default=0.0)
    pullback_depth_pct = 0.0
    rebreak_pct = 0.0
    if rebreak_reference > 0:
        pullback_depth_pct = max(
            ((rebreak_reference - completed.low) / rebreak_reference) * 100,
            0.0,
        )
        rebreak_pct = _percent_change(current_price, rebreak_reference)

    vwap_bars = ordered[-7:-1]
    vwap_volume = sum(bar.volume for bar in vwap_bars if bar.volume > 0)
    if vwap_volume > 0:
        vwap = sum(bar.close * bar.volume for bar in vwap_bars if bar.volume > 0) / vwap_volume
    else:
        vwap = sum(bar.close for bar in vwap_bars) / len(vwap_bars)

    return MinuteMomentum(
        relative_volume=relative_volume,
        one_minute_change_pct=_percent_change(completed.close, previous.close),
        five_minute_change_pct=_percent_change(completed.close, five_minutes_ago.close),
        breakout_pct=breakout_pct,
        vwap_extension_pct=_percent_change(current_price, vwap),
        confirmation_bars=len(ordered),
        volume_acceleration=volume_acceleration,
        pullback_depth_pct=pullback_depth_pct,
        rebreak_pct=rebreak_pct,
    )


def _passes_preliminary_filter(signal: MarketSignal, rules: StrategyRules) -> bool:
    return (
        signal.price > 0
        and rules.entry_min_change_pct <= signal.change_pct <= rules.entry_max_change_pct
        and signal.trading_value_krw >= rules.entry_min_trading_value_krw
    )


def _preliminary_score(signal: MarketSignal) -> float:
    change_quality = max(0.0, 12.0 - abs(signal.change_pct - 6.0))
    liquidity_quality = log10(max(signal.trading_value_krw, 1.0))
    return (change_quality * 10) + liquidity_quality


def _percent_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return ((current - previous) / previous) * 100
