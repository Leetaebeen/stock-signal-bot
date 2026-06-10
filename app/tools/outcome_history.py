import argparse
import json

from app.config import get_settings
from app.db import get_signal_outcome_history, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Show signal outcome tracking history.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--market", choices=["KR", "US"], default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--json", action="store_true", help="Print raw JSON rows.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)
    rows = get_signal_outcome_history(
        settings.sqlite_path,
        limit=args.limit,
        market=args.market,
        symbol=args.symbol,
    )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("No signal outcomes.")
        return

    for row in rows:
        observed = row["observed_price"]
        pnl = row["pnl_pct"]
        observed_text = _format_price(row["market"], float(observed)) if observed is not None else "-"
        pnl_text = f"{float(pnl):+.2f}%" if pnl is not None else "-"
        print(
            f"[{row['status']}] {row['market']}:{row['symbol']} {row['name']} "
            f"horizon={row['horizon_minutes']}m due={row['due_at']}"
        )
        print(
            f"entry={_format_price(row['market'], float(row['entry_price']))} "
            f"observed={observed_text} pnl={pnl_text}"
        )
        if row["checked_at"]:
            print(f"checked_at={row['checked_at']}")
        print()


def _format_price(market: str, price: float) -> str:
    if market == "US":
        return f"${price:,.2f}"
    return f"{price:,.0f}원"


if __name__ == "__main__":
    main()
