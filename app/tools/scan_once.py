import argparse
import asyncio

from app.config import get_settings, parse_enabled_markets
from app.market_clock import is_us_market_open
from app.worker import run_once


def _open_markets(enabled_markets: set[str]) -> set[str]:
    markets = set()
    if "US" in enabled_markets and is_us_market_open():
        markets.add("US")
    return markets


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run one real US scan.")
    parser.add_argument("--send-alert", action="store_true", help="Send Telegram alert if a signal is selected.")
    args = parser.parse_args()

    settings = get_settings()
    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    markets = _open_markets(enabled_markets) if args.send_alert else enabled_markets
    if args.send_alert and not markets:
        candidate = None
    else:
        candidate = await run_once(settings, send_alert=args.send_alert, markets=markets)

    print(f"market_mode={settings.market_mode}")
    print(f"enabled_markets={','.join(sorted(enabled_markets))}")
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
    print(f"volume_ratio={snap.volume_ratio:.2f}x")
    print(f"trading_value_krw={snap.trading_value_krw:,.0f}")
    print(f"score={candidate.score}")
    print("reasons:")
    for reason in candidate.reasons:
        print(f"- {reason}")
    print("risks:")
    for risk in candidate.risks:
        print(f"- {risk}")


if __name__ == "__main__":
    asyncio.run(_main())
