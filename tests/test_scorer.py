from app.models import MarketSnapshot
from app.signals.filters import evaluate_candidate_filter, filter_candidates
from app.signals.scorer import score_snapshot
from app.signals.selector import select_strongest


def test_filter_rejects_weak_us_candidate():
    weak = MarketSnapshot(
        symbol="PENNY",
        name="Penny Stock",
        market="US",
        price=0.8,
        change_pct=0.5,
        volume_ratio=1.0,
        trading_value_krw=100_000_000,
        vwap_price=0.9,
    )

    decision = evaluate_candidate_filter(weak)

    assert not decision.passed
    assert any("1달러 미만" in risk for risk in decision.risks)


def test_filter_accepts_strong_us_candidate_with_soft_risks():
    strong = MarketSnapshot(
        symbol="WOLF",
        name="Wolfspeed",
        market="US",
        price=45.6,
        change_pct=5.02,
        volume_ratio=4.0,
        trading_value_krw=600_000_000,
        vwap_price=45.3,
    )

    decision = evaluate_candidate_filter(strong)

    assert decision.passed
    assert any("최소 유동성" in reason for reason in decision.reasons)


def test_selects_strongest_us_candidate_after_filtering():
    weak = MarketSnapshot(
        symbol="PENNY",
        name="Penny Stock",
        market="US",
        price=0.8,
        change_pct=0.5,
        volume_ratio=1.0,
        trading_value_krw=100_000_000,
        vwap_price=0.9,
    )
    strong = MarketSnapshot(
        symbol="WOLF",
        name="Wolfspeed",
        market="US",
        price=45.6,
        change_pct=5.02,
        volume_ratio=4.0,
        trading_value_krw=600_000_000,
        vwap_price=45.3,
        news_score=0.4,
    )

    candidates = [score_snapshot(snapshot) for snapshot in filter_candidates([weak, strong])]
    selected = select_strongest(candidates, min_score=70)

    assert selected is not None
    assert selected.snapshot.symbol == "WOLF"
    assert selected.score >= 70
    assert any("상대 거래량" in reason for reason in selected.reasons)
