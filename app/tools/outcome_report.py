import argparse
import json

from app.config import get_settings
from app.db import get_signal_outcome_summary, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Show signal outcome performance summary.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--market", choices=["KR", "US"], default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--json", action="store_true", help="Print raw JSON rows.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)
    rows = get_signal_outcome_summary(
        settings.sqlite_path,
        days=args.days,
        market=args.market,
        symbol=args.symbol.upper() if args.symbol else None,
    )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    print(f"성과 요약: 최근 {max(args.days, 1)}일")
    if args.market:
        print(f"시장: {args.market}")
    if args.symbol:
        print(f"종목: {args.symbol.upper()}")
    print()

    if not rows:
        print("아직 체크 완료된 성과 기록이 없습니다.")
        return

    for row in rows:
        total = int(row["total_count"])
        wins = int(row["win_count"] or 0)
        win_rate = (wins / total) * 100 if total else 0
        print(
            f"{int(row['horizon_minutes'])}분 후: "
            f"{total}건 / 승률 {win_rate:.1f}% / "
            f"평균 {float(row['avg_pnl_pct']):+.2f}% / "
            f"최고 {float(row['best_pnl_pct']):+.2f}% / "
            f"최저 {float(row['worst_pnl_pct']):+.2f}%"
        )


if __name__ == "__main__":
    main()
