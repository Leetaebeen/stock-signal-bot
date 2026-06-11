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
    assert any("2달러 미만" in risk for risk in decision.risks)


def test_filter_accepts_us_early_momentum_candidate():
    strong = MarketSnapshot(
        symbol="WOLF",
        name="Wolfspeed",
        market="US",
        price=45.6,
        change_pct=5.02,
        volume_ratio=3.2,
        trading_value_krw=600_000_000,
        vwap_price=45.3,
        exchange="NYS",
    )

    decision = evaluate_candidate_filter(strong)

    assert decision.passed
    assert any("200%~2000%" in reason for reason in decision.reasons)
    assert any("급등 초입" in reason for reason in decision.reasons)


def test_filter_rejects_already_overheated_us_candidate():
    overheated = MarketSnapshot(
        symbol="PPCB",
        name="ProPhase BioPharma",
        market="US",
        price=5.58,
        change_pct=313.33,
        volume_ratio=0.73,
        trading_value_krw=800_000_000,
        vwap_price=5.5,
    )

    decision = evaluate_candidate_filter(overheated)

    assert not decision.passed
    assert any("12% 초과" in risk or "200% 미만" in risk for risk in decision.risks)


def test_filter_rejects_us_candidate_over_2000_percent_volume_increase():
    overheated = MarketSnapshot(
        symbol="WHLR",
        name="Wheeler",
        market="US",
        price=3.2,
        change_pct=5.02,
        volume_ratio=25.0,
        trading_value_krw=600_000_000,
        vwap_price=3.1,
    )

    decision = evaluate_candidate_filter(overheated)

    assert not decision.passed
    assert any("2000% 초과" in risk for risk in decision.risks)


def test_filter_rejects_us_option_income_etf_by_symbol_and_name():
    by_symbol = MarketSnapshot(
        symbol="AMDY",
        name="YieldMax AMD Option Income Strategy",
        market="US",
        price=50.7,
        change_pct=3.16,
        volume_ratio=3.0,
        trading_value_krw=900_000_000,
        vwap_price=49.8,
    )
    by_name = MarketSnapshot(
        symbol="FAKE",
        name="Example 2x Leveraged ETF",
        market="US",
        price=10.0,
        change_pct=4.0,
        volume_ratio=4.0,
        trading_value_krw=900_000_000,
        vwap_price=9.9,
    )

    symbol_decision = evaluate_candidate_filter(by_symbol)
    name_decision = evaluate_candidate_filter(by_name)

    assert not symbol_decision.passed
    assert not name_decision.passed
    assert any("ETF" in risk for risk in symbol_decision.risks)
    assert any("ETF" in risk for risk in name_decision.risks)


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
    assert any("거래량 증가율" in reason for reason in selected.reasons)
