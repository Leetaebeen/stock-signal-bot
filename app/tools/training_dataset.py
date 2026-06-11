import argparse
import csv
import io
import json
import sys
from pathlib import Path

from app.config import get_settings
from app.db import get_training_dataset_rows, init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Export checked signal outcomes as a training dataset.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--market", choices=["KR", "US"], default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--format", choices=["csv", "json"], default="csv")
    parser.add_argument("--output", default=None, help="Output file path. Defaults to stdout.")
    args = parser.parse_args()

    settings = get_settings()
    init_db(settings.sqlite_path)
    rows = get_training_dataset_rows(
        settings.sqlite_path,
        days=args.days,
        market=args.market,
        symbol=args.symbol.upper() if args.symbol else None,
    )

    if args.format == "json":
        text = json.dumps(rows, ensure_ascii=False, indent=2)
    else:
        text = _to_csv(rows)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8", newline="")
        print(f"exported {len(rows)} rows to {output_path}")
    else:
        sys.stdout.write(text)


def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


if __name__ == "__main__":
    main()
