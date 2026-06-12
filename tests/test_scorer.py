from app.models import MarketSnapshot
from app.signals.filters import FilterConfig, evaluate_candidate_filter, filter_candidates, is_excluded_us_product
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


def test_filter_uses_custom_us_thresholds():
    early = MarketSnapshot(
        symbol="EARLY",
        name="Early Momentum",
        market="US",
        price=3.0,
        change_pct=1.7,
        volume_ratio=1.7,
        trading_value_krw=400_000_000,
        vwap_price=2.95,
    )
    strict_decision = evaluate_candidate_filter(early)
    loose_decision = evaluate_candidate_filter(
        early,
        FilterConfig(
            us_volume_ratio_min=1.5,
            us_volume_ratio_max=20.0,
            us_change_pct_min=1.5,
            us_change_pct_max=12.0,
            us_min_trading_value_krw=300_000_000,
            us_min_price=2.0,
        ),
    )

    assert not strict_decision.passed
    assert loose_decision.passed


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


def test_filter_accepts_us_explosion_candidate():
    explosion = MarketSnapshot(
        symbol="BOOM",
        name="Boom Digital Holdings",
        market="US",
        price=3.2,
        change_pct=44.0,
        volume_ratio=2.5,
        trading_value_krw=800_000_000,
        vwap_price=3.0,
    )

    decision = evaluate_candidate_filter(explosion)
    candidate = score_snapshot(explosion)

    assert decision.passed
    assert any("explosion mode" in reason for reason in decision.reasons)
    assert candidate.score >= 70


def test_score_prioritizes_liquid_explosion_candidate():
    explosion = MarketSnapshot(
        symbol="BYAH",
        name="Park Ha Biological Technology",
        market="US",
        price=2.68,
        change_pct=155.24,
        volume_ratio=1.25,
        trading_value_krw=37_500_000_000,
        vwap_price=2.4,
    )

    candidate = score_snapshot(explosion)

    assert candidate.score >= 80


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
    assert is_excluded_us_product(by_symbol)
    assert is_excluded_us_product(by_name)


def test_filter_rejects_us_etf_brand_names():
    ishares = MarketSnapshot(
        symbol="ECH",
        name="iShares MSCI Chile Capped",
        market="US",
        price=32.0,
        change_pct=2.5,
        volume_ratio=3.0,
        trading_value_krw=900_000_000,
        vwap_price=31.8,
    )
    spdr = MarketSnapshot(
        symbol="TFI",
        name="SPDR Nuveen Bloomberg Barclays Municipal Bond",
        market="US",
        price=48.0,
        change_pct=2.5,
        volume_ratio=3.0,
        trading_value_krw=900_000_000,
        vwap_price=47.8,
    )

    assert not evaluate_candidate_filter(ishares).passed
    assert not evaluate_candidate_filter(spdr).passed
    assert is_excluded_us_product(ishares)
    assert is_excluded_us_product(spdr)


def test_filter_rejects_us_preferred_and_closed_end_fund_names():
    preferred = MarketSnapshot(
        symbol="STRK",
        name="Strategy Strike Preferred Shares",
        market="US",
        price=90.0,
        change_pct=2.5,
        volume_ratio=3.0,
        trading_value_krw=900_000_000,
        vwap_price=89.8,
    )
    closed_end_fund = MarketSnapshot(
        symbol="RQI",
        name="Cohen & Steers Quality Income Realty",
        market="US",
        price=13.0,
        change_pct=2.5,
        volume_ratio=3.0,
        trading_value_krw=900_000_000,
        vwap_price=12.8,
    )

    assert not evaluate_candidate_filter(preferred).passed
    assert not evaluate_candidate_filter(closed_end_fund).passed
    assert is_excluded_us_product(preferred)
    assert is_excluded_us_product(closed_end_fund)


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
