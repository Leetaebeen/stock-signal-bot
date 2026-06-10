import argparse
import asyncio

from app.ai.analyst import analyze_candidate
from app.config import get_settings
from app.models import MarketSnapshot, SignalCandidate


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Check AI analysis provider connection.")
    parser.add_argument("--symbol", default="005930")
    parser.add_argument("--name", default="삼성전자")
    args = parser.parse_args()

    settings = get_settings()
    candidate = SignalCandidate(
        snapshot=MarketSnapshot(
            symbol=args.symbol,
            name=args.name,
            market="KR",
            price=80000,
            change_pct=3.2,
            volume_ratio=3.8,
            trading_value_krw=120_000_000_000,
            high_price=80800,
            vwap_price=79000,
        ),
        score=82,
        reasons=["거래량 증가", "거래대금 충분", "VWAP 위에서 유지"],
        risks=["테스트 데이터이므로 실제 매매 판단에 사용하지 않음"],
    )

    analyzed = await analyze_candidate(candidate, settings)
    analysis = analyzed.ai_analysis

    print(f"enabled={settings.ai_analysis_enabled}")
    print(f"provider={settings.ai_provider}")
    print(f"model={settings.ai_model or 'default'}")
    if analysis is None:
        print("analysis=None")
        return
    print(f"recommendation={analysis.recommendation}")
    print(f"confidence={analysis.confidence}")
    print(f"summary={analysis.summary}")
    print("key_points:")
    for point in analysis.key_points:
        print(f"- {point}")
    print("risk_notes:")
    for risk in analysis.risk_notes:
        print(f"- {risk}")


if __name__ == "__main__":
    asyncio.run(_main())
