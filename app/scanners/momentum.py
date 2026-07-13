from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Iterable, Protocol

from app.brokers.kis_client import PriceSnapshot
from app.trading.strategy import KST, MarketSignal, StrategyRules, entry_score


logger = logging.getLogger(__name__)


class QuoteClient(Protocol):
    def get_domestic_price(self, symbol: str, name: str | None = None) -> PriceSnapshot:
        ...

    def get_overseas_price(self, symbol: str, exchange: str = "NAS", name: str | None = None) -> PriceSnapshot:
        ...


@dataclass(frozen=True)
class ScanCandidate:
    signal: MarketSignal
    source: str
    score: float


class TradingValueBaseline:
    def __init__(self) -> None:
        self._values: dict[str, float] = {}

    def volume_ratio(self, symbol: str, current_trading_value_krw: float) -> float:
        previous = self._values.get(symbol)
        self._values[symbol] = max(current_trading_value_krw, 0)
        if previous is None or previous <= 0:
            return 1.0
        if current_trading_value_krw <= 0:
            return 1.0
        return max(current_trading_value_krw / previous, 1.0)


class MomentumScanner:
    def __init__(
        self,
        *,
        quote_client: QuoteClient,
        baseline: TradingValueBaseline | None = None,
        exchange: str = "NAS",
        request_delay_seconds: float = 0.0,
    ) -> None:
        self.quote_client = quote_client
        self.baseline = baseline or TradingValueBaseline()
        self.exchange = exchange
        self.request_delay_seconds = request_delay_seconds

    def scan_us(self, symbols: Iterable[str], limit: int = 5) -> list[ScanCandidate]:
        return self._scan(symbols, market="US", limit=limit)

    def scan_kr(self, symbols: Iterable[str], limit: int = 5) -> list[ScanCandidate]:
        return self._scan(symbols, market="KR", limit=limit)

    def _scan(self, symbols: Iterable[str], *, market: str, limit: int) -> list[ScanCandidate]:
        candidates: list[ScanCandidate] = []
        observed_at = datetime.now(KST)
        for symbol in _clean_symbols(symbols):
            if self.request_delay_seconds > 0:
                time.sleep(self.request_delay_seconds)
            try:
                if market == "KR":
                    snapshot = self.quote_client.get_domestic_price(symbol)
                else:
                    snapshot = self.quote_client.get_overseas_price(symbol, exchange=self.exchange)
            except Exception as exc:
                logger.warning("quote skipped symbol=%s reason=%s", symbol, exc)
                continue
            volume_ratio = self.baseline.volume_ratio(snapshot.symbol, snapshot.trading_value_krw)
            signal = MarketSignal(
                symbol=snapshot.symbol,
                name=snapshot.name,
                market=market,
                price=snapshot.price,
                change_pct=snapshot.change_pct,
                volume_ratio=volume_ratio,
                trading_value_krw=snapshot.trading_value_krw,
                observed_at=observed_at,
            )
            candidates.append(
                ScanCandidate(
                    signal=signal,
                    source=f"kis_{market.lower()}_quote",
                    score=_score_signal(signal),
                )
            )
        return sorted(candidates, key=lambda candidate: candidate.score, reverse=True)[:limit]


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


def _score_signal(signal: MarketSignal) -> float:
    return float(entry_score(signal, StrategyRules()))
