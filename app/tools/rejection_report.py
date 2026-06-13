import argparse
import asyncio
import json

from app.config import get_settings, parse_enabled_markets
from app.signals.filters import filter_config_from_settings
from app.signals.rejection_report import RISK_LABELS, build_rejection_report
from app.worker import build_market_client


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Show why current US scan candidates are rejected.")
    parser.add_argument("--market", choices=["US"], default=None)
    parser.add_argument("--near-miss-limit", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Print raw JSON report.")
    args = parser.parse_args()

    settings = get_settings()
    client = build_market_client(settings)
    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    markets = {args.market} if args.market else enabled_markets
    markets &= enabled_markets

    snapshots = []
    if "US" in markets:
        snapshots.extend(await client.get_us_snapshots())

    report = build_rejection_report(
        snapshots,
        near_miss_limit=args.near_miss_limit,
        filter_config=filter_config_from_settings(settings),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"market_mode={settings.market_mode}")
    print(f"markets={','.join(sorted(markets)) if markets else 'none'}")
    print(f"total={report['total']} passed={report['passed_count']} rejected={report['rejected_count']}")
    print()
    print("제외 사유 집계:")
    if not report["risk_counts"]:
        print("- 없음")
    for category, count in report["risk_counts"].items():
        print(f"- {RISK_LABELS.get(category, category)}: {count}개")

    print()
    print("아깝게 제외된 후보:")
    if not report["near_misses"]:
        print("- 없음")
    for row in report["near_misses"]:
        print(
            f"- {row['market']}:{row['symbol']} {row['name']} "
            f"score={row['score']} change={row['change_pct']:+.2f}% "
            f"vol={row['volume_ratio']:.1f}x value={row['trading_value_krw'] / 100_000_000:,.0f}억원"
        )
        print(f"  제외: {', '.join(row['risk_labels'])}")

    print()
    print("통과 후보:")
    if not report["top_passed"]:
        print("- 없음")
    for row in report["top_passed"]:
        print(
            f"- {row['market']}:{row['symbol']} {row['name']} "
            f"score={row['score']} change={row['change_pct']:+.2f}% "
            f"vol={row['volume_ratio']:.1f}x value={row['trading_value_krw'] / 100_000_000:,.0f}억원"
        )


if __name__ == "__main__":
    asyncio.run(_main())
