import asyncio
import argparse

from app.config import get_settings
from app.market_clock import is_kr_regular_market_open, is_us_market_open
from app.worker import run_once


def _open_markets() -> set[str]:
    markets = set()
    if is_kr_regular_market_open():
        markets.add("KR")
    if is_us_market_open():
        markets.add("US")
    return markets


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run one real scan.")
    parser.add_argument("--send-alert", action="store_true", help="Send Telegram alert if a signal is selected.")
    args = parser.parse_args()

    settings = get_settings()
    markets = _open_markets() if args.send_alert else None
    if args.send_alert and not markets:
        candidate = None
    else:
        candidate = await run_once(settings, send_alert=args.send_alert, markets=markets)
    print(f"market_mode={settings.market_mode}")
    print(f"send_alert={args.send_alert}")
    if args.send_alert:
        print(f"alert_markets={','.join(sorted(markets)) if markets else 'none'}")
    if candidate is None:
        print("selected=None")
        return
    snap = candidate.snapshot
    print(f"selected={snap.market}:{snap.symbol} {snap.name}")
    print(f"price={snap.price:,.2f}")
    print(f"change_pct={snap.change_pct:+.2f}")
    print(f"trading_value_krw={snap.trading_value_krw:,.0f}")
    print(f"score={candidate.score}")
    if candidate.ai_analysis:
        analysis = candidate.ai_analysis
        print("ai_analysis:")
        print(f"  recommendation={analysis.recommendation}")
        print(f"  confidence={analysis.confidence}")
        print(f"  summary={analysis.summary}")
        print("  key_points:")
        for point in analysis.key_points:
            print(f"  - {point}")
        print("  risk_notes:")
        for risk in analysis.risk_notes:
            print(f"  - {risk}")
    print("reasons:")
    for reason in candidate.reasons:
        print(f"- {reason}")
    print("risks:")
    for risk in candidate.risks:
        print(f"- {risk}")


if __name__ == "__main__":
    asyncio.run(_main())
