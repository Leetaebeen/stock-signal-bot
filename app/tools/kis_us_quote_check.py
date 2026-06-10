import argparse

from app.brokers.kis_client import KisClient, _overseas_output_to_snapshot
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a KIS overseas stock quote.")
    parser.add_argument("symbol", help="US stock ticker, for example NVDA or AAPL")
    parser.add_argument("--exchange", default="NAS", help="KIS exchange code: NAS, NYS, AMS")
    parser.add_argument("--name", default=None, help="Optional display name")
    parser.add_argument("--raw", action="store_true", help="Print selected raw KIS output fields.")
    args = parser.parse_args()

    settings = get_settings()
    client = KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    payload = None
    if args.raw:
        payload = client.get_overseas_price_raw(args.symbol.upper(), exchange=args.exchange.upper())
        snapshot = _overseas_output_to_snapshot(args.symbol.upper(), args.name, payload.get("output") or {})
    else:
        snapshot = client.get_overseas_price(args.symbol.upper(), exchange=args.exchange.upper(), name=args.name)

    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"exchange={args.exchange.upper()}")
    print(f"{snapshot.name} ({snapshot.symbol})")
    print(f"현재가: ${snapshot.price:,.2f}")
    print(f"등락률: {snapshot.change_pct:+.2f}%")
    print(f"거래대금 KRW 환산: {snapshot.trading_value_krw / 1_000_000_000:,.1f}B")

    if args.raw:
        output = payload.get("output") or {}
        keys = [
            "rsym",
            "last",
            "sign",
            "diff",
            "rate",
            "open",
            "high",
            "low",
            "base",
            "tvol",
            "tamt",
            "xymd",
            "xhms",
        ]
        print("raw:")
        for key in keys:
            print(f"  {key}={output.get(key)}")


if __name__ == "__main__":
    main()
