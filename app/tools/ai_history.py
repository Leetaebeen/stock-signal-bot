import argparse
import json

from app.config import get_settings
from app.db import get_ai_analysis_history, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Show recent AI analysis history.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--market", choices=["KR", "US"], default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--json", action="store_true", help="Print raw JSON rows.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)
    rows = get_ai_analysis_history(
        settings.sqlite_path,
        limit=args.limit,
        market=args.market,
        symbol=args.symbol,
    )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("AI analysis history is empty.")
        return

    for row in rows:
        key_points = _load_list(row["key_points"])
        risk_notes = _load_list(row["risk_notes"])
        print(
            f"[{row['created_at']}] {row['market']}:{row['symbol']} "
            f"score={row['score']} ai={row['recommendation']} confidence={row['confidence']}"
        )
        print(f"summary={row['summary']}")
        if key_points:
            print("key_points:")
            for point in key_points:
                print(f"- {point}")
        if risk_notes:
            print("risk_notes:")
            for risk in risk_notes:
                print(f"- {risk}")
        print()


def _load_list(value: str) -> list[str]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


if __name__ == "__main__":
    main()
