from dataclasses import dataclass, asdict
from typing import Any, Literal

Market = Literal["US"]


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    name: str
    market: Market
    price: float
    change_pct: float
    volume_ratio: float
    trading_value_krw: float
    price_krw: float | None = None
    vi_gap_pct: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    vwap_price: float | None = None
    foreign_flow_score: float = 0.0
    institution_flow_score: float = 0.0
    program_flow_score: float = 0.0
    news_score: float = 0.0
    disclosure_risk: float = 0.0
    exchange: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SignalCandidate:
    snapshot: MarketSnapshot
    score: int
    reasons: list[str]
    risks: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "score": self.score,
            "reasons": self.reasons,
            "risks": self.risks,
        }
