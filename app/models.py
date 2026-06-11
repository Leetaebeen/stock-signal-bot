from dataclasses import dataclass, asdict
from typing import Any, Literal

Market = Literal["KR", "US"]
AIRecommendation = Literal["BUY", "WATCH", "SKIP"]


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    name: str
    market: Market
    price: float
    change_pct: float
    volume_ratio: float
    trading_value_krw: float
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
class AIAnalysis:
    recommendation: AIRecommendation
    confidence: int
    summary: str
    key_points: list[str]
    risk_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SignalCandidate:
    snapshot: MarketSnapshot
    score: int
    reasons: list[str]
    risks: list[str]
    ai_analysis: AIAnalysis | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "score": self.score,
            "reasons": self.reasons,
            "risks": self.risks,
            "ai_analysis": self.ai_analysis.to_dict() if self.ai_analysis else None,
        }


@dataclass(frozen=True)
class TradePlan:
    entry_price: float
    current_price: float
    target_price: float
    stop_price: float
    expected_profit_pct: float
    stop_loss_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
