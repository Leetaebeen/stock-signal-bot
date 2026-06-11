import argparse
import json

from app.config import get_settings
from app.db import get_scan_rejection_summary, init_db
from app.signals.rejection_report import RISK_LABELS


def main() -> None:
    parser = argparse.ArgumentParser(description="Show accumulated scan rejection summary.")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="Print raw JSON summary.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)
    summary = get_scan_rejection_summary(settings.sqlite_path, days=args.days)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print(f"누적 탈락 리포트: 최근 {summary['days']}일")
    print(f"스캔 수: {summary['scan_count']}")
    print(
        f"후보: {summary['total_count']}개 / "
        f"통과: {summary['passed_count']}개 / "
        f"탈락: {summary['rejected_count']}개 / "
        f"통과율: {summary['pass_rate_pct']:.2f}%"
    )
    print()
    print("탈락 사유 누적:")
    if not summary["risk_counts"]:
        print("- 없음")
    for category, count in summary["risk_counts"].items():
        print(f"- {RISK_LABELS.get(category, category)}: {count}개")

    print()
    print("튜닝 힌트:")
    for hint in _build_hints(summary):
        print(f"- {hint}")


def _build_hints(summary: dict) -> list[str]:
    if summary["scan_count"] == 0:
        return ["아직 누적된 스캔 기록이 없습니다."]

    hints = []
    risk_counts = summary["risk_counts"]
    total = max(int(summary["total_count"]), 1)
    pass_rate = float(summary["pass_rate_pct"])

    if pass_rate == 0:
        hints.append("통과 후보가 전혀 없습니다. 조건 완화 후보를 검토하세요.")
    elif pass_rate < 2:
        hints.append("통과율이 낮습니다. 알림이 너무 드물면 조건을 소폭 완화할 수 있습니다.")

    if risk_counts.get("change_too_low", 0) / total >= 0.5:
        hints.append("등락률 2% 미만 탈락이 많습니다. 너무 조기 포착을 원하면 1.5% 기준을 검토하세요.")
    if risk_counts.get("trading_value_too_low", 0) / total >= 0.3:
        hints.append("거래대금 부족 탈락이 많습니다. 단, 유동성 안전을 위해 5억 기준은 신중히 낮추세요.")
    if risk_counts.get("vwap_break", 0) / total >= 0.3:
        hints.append("VWAP 이탈 탈락이 많습니다. 이 조건은 추세 품질 필터라 유지하는 편이 좋습니다.")
    if risk_counts.get("volume_too_high", 0) / total >= 0.3:
        hints.append("거래량 2000% 초과가 많습니다. 이미 과열된 종목을 거르는 효과가 큽니다.")
    if risk_counts.get("excluded_product", 0) > 0:
        hints.append("ETF/파생형 상품이 계속 섞입니다. 발견되는 상품명 키워드를 제외 목록에 추가하세요.")

    return hints or ["현재 누적 조건은 특별히 조정할 신호가 약합니다."]


if __name__ == "__main__":
    main()
