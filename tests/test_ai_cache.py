from dataclasses import replace

from app.db import count_ai_analysis_today, get_ai_analysis_history, get_recent_ai_analysis, init_db, save_ai_analysis
from app.models import AIAnalysis, MarketSnapshot
from app.signals.scorer import score_snapshot


def test_ai_analysis_cache_roundtrip(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))
    candidate = score_snapshot(
        MarketSnapshot(
            symbol="005930",
            name="삼성전자",
            market="KR",
            price=80000,
            change_pct=3.0,
            volume_ratio=4.0,
            trading_value_krw=120_000_000_000,
        )
    )
    analysis = AIAnalysis(
        recommendation="BUY",
        confidence=88,
        summary="거래대금과 거래량이 양호합니다.",
        key_points=["거래량 증가"],
        risk_notes=["추격 매수 주의"],
    )

    save_ai_analysis(str(db_path), replace(candidate, ai_analysis=analysis))

    cached = get_recent_ai_analysis(str(db_path), "KR", "005930", ttl_minutes=60)
    assert cached is not None
    assert cached.recommendation == "BUY"
    assert cached.confidence == 88
    assert cached.key_points == ["거래량 증가"]
    assert count_ai_analysis_today(str(db_path)) == 1


def test_empty_ai_analysis_cache_returns_none(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))

    assert get_recent_ai_analysis(str(db_path), "KR", "005930", ttl_minutes=60) is None
    assert count_ai_analysis_today(str(db_path)) == 0


def test_ai_analysis_history_filters_by_market_and_symbol(tmp_path):
    db_path = tmp_path / "signals.db"
    init_db(str(db_path))
    analysis = AIAnalysis(
        recommendation="BUY",
        confidence=88,
        summary="양호",
        key_points=["거래량 증가"],
        risk_notes=[],
    )
    kr_candidate = score_snapshot(
        MarketSnapshot(
            symbol="005930",
            name="삼성전자",
            market="KR",
            price=80000,
            change_pct=3.0,
            volume_ratio=4.0,
            trading_value_krw=120_000_000_000,
        )
    )
    us_candidate = score_snapshot(
        MarketSnapshot(
            symbol="NVDA",
            name="NVIDIA",
            market="US",
            price=150,
            change_pct=3.0,
            volume_ratio=4.0,
            trading_value_krw=1_000_000_000_000,
        )
    )

    save_ai_analysis(str(db_path), replace(kr_candidate, ai_analysis=analysis))
    save_ai_analysis(str(db_path), replace(us_candidate, ai_analysis=analysis))

    kr_rows = get_ai_analysis_history(str(db_path), market="KR")
    nvda_rows = get_ai_analysis_history(str(db_path), symbol="NVDA")

    assert len(kr_rows) == 1
    assert kr_rows[0]["symbol"] == "005930"
    assert len(nvda_rows) == 1
    assert nvda_rows[0]["market"] == "US"
