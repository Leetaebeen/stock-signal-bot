from app.models import MarketSnapshot
from app.signals.rejection_report import build_rejection_report


def test_rejection_report_counts_us_filter_reasons():
    low_price = MarketSnapshot(
        symbol="PENNY",
        name="Penny Stock",
        market="US",
        price=0.8,
        change_pct=0.5,
        volume_ratio=1.0,
        trading_value_krw=100_000_000,
        vwap_price=0.9,
    )
    etf = MarketSnapshot(
        symbol="AMDY",
        name="YieldMax AMD Option Income Strategy",
        market="US",
        price=50.7,
        change_pct=3.16,
        volume_ratio=3.0,
        trading_value_krw=900_000_000,
        vwap_price=49.8,
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
    )

    report = build_rejection_report([low_price, etf, strong])

    assert report["total"] == 3
    assert report["passed_count"] == 1
    assert report["rejected_count"] == 2
    assert report["risk_counts"]["price_too_low"] == 1
    assert report["risk_counts"]["excluded_product"] == 1
    assert report["top_passed"][0]["symbol"] == "WOLF"
