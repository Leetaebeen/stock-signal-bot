import argparse
import json

from app.config import get_settings
from app.db import get_signal_state_history, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Show active or recent tracked signal states.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--all", action="store_true", help="Show all recent states, including closed states.")
    parser.add_argument("--market", choices=["KR", "US"], default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--json", action="store_true", help="Print raw JSON rows.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)
    rows = get_signal_state_history(
        settings.sqlite_path,
        limit=args.limit,
        active_only=not args.all,
        market=args.market,
        symbol=args.symbol,
    )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        scope = "active" if not args.all else "tracked"
        print(f"No {scope} signal states.")
        return

    for row in rows:
        entry = float(row["entry_price"])
        current = float(row["current_price"])
        target = float(row["target_price"])
        stop = float(row["stop_price"])
        pnl_pct = ((current - entry) / entry) * 100 if entry else 0
        target_gap_pct = ((target - current) / current) * 100 if current else 0
        stop_gap_pct = ((current - stop) / current) * 100 if current else 0

        print(
            f"[{row['status']}] {row['market']}:{row['symbol']} {row['name']} "
            f"score={row['score']} updated={row['updated_at']}"
        )
        print(
            f"entry={_format_price(row['market'], entry)} "
            f"current={_format_price(row['market'], current)} "
            f"pnl={pnl_pct:+.2f}%"
        )
        print(
            f"target={_format_price(row['market'], target)} "
            f"target_gap={target_gap_pct:+.2f}% "
            f"stop={_format_price(row['market'], stop)} "
            f"stop_gap={stop_gap_pct:+.2f}%"
        )
        print()


def _format_price(market: str, price: float) -> str:
    if market == "US":
        return f"${price:,.2f}"
    return f"{price:,.0f}원"


if __name__ == "__main__":
    main()
