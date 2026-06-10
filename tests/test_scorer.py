from app.models import MarketSnapshot
from app.signals.filters import evaluate_candidate_filter, filter_candidates
from app.signals.scorer import score_snapshot
from app.signals.selector import select_strongest


def test_filter_rejects_weak_candidate():
    weak = MarketSnapshot(
        symbol="AAA",
        name="Weak",
        market="KR",
        price=1_000,
        change_pct=1.0,
        volume_ratio=1.0,
        trading_value_krw=1_000_000_000,
        high_price=1_100,
        vwap_price=1_050,
    )

    decision = evaluate_candidate_filter(weak)

    assert not decision.passed
    assert decision.risks


def test_filter_accepts_strong_candidate():
    strong = MarketSnapshot(
        symbol="BBB",
        name="Strong",
        market="KR",
        price=1_000,
        change_pct=5.0,
        volume_ratio=5.0,
        trading_value_krw=160_000_000_000,
        high_price=1_010,
        vwap_price=980,
    )

    decision = evaluate_candidate_filter(strong)

    assert decision.passed
    assert any("거래대금" in reason for reason in decision.reasons)


def test_selects_strongest_candidate_after_filtering():
    weak = MarketSnapshot(
        symbol="AAA",
        name="Weak",
        market="KR",
        price=1_000,
        change_pct=1.0,
        volume_ratio=1.0,
        trading_value_krw=1_000_000_000,
        high_price=1_100,
        vwap_price=1_050,
    )
    strong = MarketSnapshot(
        symbol="BBB",
        name="Strong",
        market="KR",
        price=1_000,
        change_pct=5.0,
        volume_ratio=5.0,
        trading_value_krw=160_000_000_000,
        high_price=1_010,
        vwap_price=980,
        foreign_flow_score=0.5,
        institution_flow_score=0.5,
        program_flow_score=0.5,
    )

    candidates = [score_snapshot(snapshot) for snapshot in filter_candidates([weak, strong])]
    selected = select_strongest(candidates, min_score=80)

    assert selected is not None
    assert selected.snapshot.symbol == "BBB"
    assert selected.score >= 80
    assert any("거래량" in reason for reason in selected.reasons)
