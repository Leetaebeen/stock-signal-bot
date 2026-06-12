import asyncio
import argparse
from pathlib import Path

from app.brokers.toss_client import TossClient
from app.brokers.toss_rank_client import TossRankClient
from app.config import get_settings
from app.signals.filters import evaluate_candidate_filter, filter_candidates, filter_config_from_settings
from app.signals.scorer import score_snapshot
from app.signals.selector import select_strongest


async def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--reset-cursor", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if args.reset_cursor:
        cursor_path = Path(settings.toss_scan_cursor_path)
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        cursor_path.write_text("0", encoding="utf-8")
        print(f"cursor_reset={cursor_path}")

    toss_client = TossClient(
        api_key=settings.toss_api_key,
        secret_key=settings.toss_secret_key,
        base_url=settings.toss_base_url,
        token_cache_path=settings.toss_token_cache_path,
    )
    client = TossRankClient(
        toss_client=toss_client,
        request_interval_seconds=settings.toss_request_interval_seconds,
        rank_count=args.count or settings.toss_rank_count,
        us_symbols_path=settings.us_symbols_path,
        scan_cursor_path=settings.toss_scan_cursor_path,
        spike_cache_path=settings.toss_spike_cache_path,
        price_sweep_count=settings.toss_price_sweep_count,
        spike_1m_pct=settings.toss_spike_1m_pct,
        spike_5m_pct=settings.toss_spike_5m_pct,
        spike_20m_pct=settings.toss_spike_20m_pct,
        spike_max_candidates=settings.toss_spike_max_candidates,
    )
    snapshots = await client.get_us_snapshots()
    filtered = filter_candidates(snapshots, filter_config_from_settings(settings))
    candidates = [score_snapshot(snapshot) for snapshot in filtered]
    selected = select_strongest(candidates, min_score=settings.min_alert_score)

    print(f"raw_snapshots={len(snapshots)}")
    print(f"filter_passed={len(filtered)}")
    print(f"scored={len(candidates)}")
    if selected:
        snap = selected.snapshot
        print(f"selected={snap.symbol} {snap.name} score={selected.score}")
    else:
        print("selected=None")

    print("[raw top]")
    for snapshot in snapshots[:10]:
        status = _filter_status(snapshot, settings)
        print(
            f"{snapshot.symbol} {snapshot.name} "
            f"price={snapshot.price:.2f} change={snapshot.change_pct:+.2f}% "
            f"volume={snapshot.volume_ratio:.2f}x value_krw={snapshot.trading_value_krw:,.0f} "
            f"{status}"
        )

    if filtered:
        print("[filter passed]")
        for snapshot in filtered[:10]:
            print(
                f"{snapshot.symbol} {snapshot.name} "
                f"price={snapshot.price:.2f} change={snapshot.change_pct:+.2f}% "
                f"volume={snapshot.volume_ratio:.2f}x value_krw={snapshot.trading_value_krw:,.0f}"
            )


def _filter_status(snapshot, settings) -> str:
    decision = evaluate_candidate_filter(snapshot, filter_config_from_settings(settings))
    if decision.passed:
        return "PASS"

    reasons = []
    if snapshot.change_pct < settings.us_filter_change_pct_min:
        reasons.append(f"change<{settings.us_filter_change_pct_min:.1f}%")
    elif snapshot.change_pct > settings.us_filter_change_pct_max:
        reasons.append(f"change>{settings.us_filter_change_pct_max:.1f}%")

    if snapshot.volume_ratio < settings.us_filter_volume_ratio_min:
        reasons.append(f"volume<{settings.us_filter_volume_ratio_min:.1f}x")
    elif snapshot.volume_ratio > settings.us_filter_volume_ratio_max:
        reasons.append(f"volume>{settings.us_filter_volume_ratio_max:.1f}x")

    if snapshot.trading_value_krw < settings.us_filter_min_trading_value_krw:
        reasons.append(f"value<{settings.us_filter_min_trading_value_krw:,.0f}KRW")

    if snapshot.price < settings.us_filter_min_price:
        reasons.append(f"price<{settings.us_filter_min_price:.2f}")

    if not reasons:
        return "PASS"
    return "REJECT(" + ",".join(reasons) + ")"


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
