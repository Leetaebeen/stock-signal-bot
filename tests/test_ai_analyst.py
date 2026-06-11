from app.ai.analyst import ai_allows_alert, extract_gemini_text, parse_ai_analysis
from app.models import MarketSnapshot, SignalCandidate


def test_parse_ai_analysis_reads_strict_json():
    analysis = parse_ai_analysis(
        """
        {
          "recommendation": "BUY",
          "confidence": 82,
          "summary": "거래량과 VWAP 흐름이 양호합니다.",
          "key_points": ["거래량 증가", "VWAP 위 유지"],
          "risk_notes": ["추격 매수 주의"]
        }
        """
    )

    assert analysis.recommendation == "BUY"
    assert analysis.confidence == 82
    assert analysis.key_points == ["거래량 증가", "VWAP 위 유지"]
    assert analysis.risk_notes == ["추격 매수 주의"]


def test_extract_gemini_text_reads_candidate_parts():
    payload = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"recommendation":"BUY","confidence":80,'
                                '"summary":"양호","key_points":["거래량"],"risk_notes":[]}'
                            )
                        }
                    ]
                }
            }
        ]
    }

    assert '"recommendation":"BUY"' in extract_gemini_text(payload)


def test_ai_allows_alert_only_for_buy_with_enough_confidence():
    snapshot = MarketSnapshot(
        symbol="005930",
        name="삼성전자",
        market="KR",
        price=80000,
        change_pct=3.0,
        volume_ratio=3.0,
        trading_value_krw=100_000_000_000,
    )
    analysis = parse_ai_analysis(
        '{"recommendation":"WATCH","confidence":90,"summary":"관망","key_points":[],"risk_notes":[]}'
    )
    candidate = SignalCandidate(snapshot=snapshot, score=80, reasons=[], risks=[], ai_analysis=analysis)

    assert not ai_allows_alert(candidate, min_confidence=70)
