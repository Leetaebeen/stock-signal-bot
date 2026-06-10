import argparse

from app.config import get_settings
from app.db import clear_signal_states, get_signal_state_history, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear tracked signal states by marking them as CLEARED.")
    parser.add_argument("symbol", nargs="?", default=None)
    parser.add_argument("--market", choices=["KR", "US"], default=None)
    parser.add_argument("--all", action="store_true", help="Clear all matching states, including closed states.")
    parser.add_argument("--yes", action="store_true", help="Apply changes. Without this, only prints a dry run.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)

    rows = get_signal_state_history(
        settings.sqlite_path,
        limit=100,
        active_only=not args.all,
        market=args.market,
        symbol=args.symbol,
    )
    if not rows:
        print("No matching signal states.")
        return

    print("Matching signal states:")
    for row in rows:
        print(f"- id={row['id']} {row['market']}:{row['symbol']} {row['name']} status={row['status']}")

    if not args.yes:
        print("\ndry_run=True")
        print("Add --yes to mark these states as CLEARED.")
        return

    count = clear_signal_states(
        settings.sqlite_path,
        market=args.market,
        symbol=args.symbol,
        active_only=not args.all,
    )
    print(f"cleared={count}")


if __name__ == "__main__":
    main()
