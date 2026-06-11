import asyncio

from app.config import get_settings, parse_enabled_markets
from app.signals.filters import evaluate_candidate_filter
from app.signals.scorer import score_snapshot
from app.worker import build_market_client


async def _main() -> None:
    settings = get_settings()
    client = build_market_client(settings)
    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    snapshots = []
    if "KR" in enabled_markets:
        snapshots.extend(await client.get_kr_snapshots())
    if "US" in enabled_markets:
        snapshots.extend(await client.get_us_snapshots())

    print(f"market_mode={settings.market_mode}")
    print(f"enabled_markets={','.join(sorted(enabled_markets))}")
    print(f"snapshots={len(snapshots)}")
    for snapshot in snapshots[:20]:
        decision = evaluate_candidate_filter(snapshot)
        candidate = score_snapshot(snapshot)
        print(
            f"{snapshot.market}:{snapshot.symbol} {snapshot.name} "
            f"price={snapshot.price:,.2f} change={snapshot.change_pct:+.2f}% "
            f"value={snapshot.trading_value_krw / 100_000_000:,.0f}억 "
            f"volume_ratio={snapshot.volume_ratio:.1f} "
            f"high={snapshot.high_price or 0:,.2f} vwap={snapshot.vwap_price or 0:,.2f} "
            f"score={candidate.score} passed={decision.passed}"
        )
        if decision.risks:
            print(f"  filter_risks={'; '.join(decision.risks)}")
        if candidate.reasons:
            print(f"  score_reasons={'; '.join(candidate.reasons[:4])}")


if __name__ == "__main__":
    asyncio.run(_main())
