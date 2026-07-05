import argparse

from app.brokers.kis_client import KisClient
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a KIS paper quote without placing orders.")
    parser.add_argument("symbol", help="US symbol like NVDA, or Korean stock code like 005930")
    parser.add_argument("--market", choices=["US", "KR"], default="US")
    parser.add_argument("--exchange", default="NAS", help="US exchange code, for example NAS, NYS, AMS")
    parser.add_argument("--name", default=None, help="Optional display name")
    args = parser.parse_args()

    settings = get_settings()
    client = KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        account_product_code=settings.kis_account_product_code,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    client.assert_readonly_paper_mode(
        paper_trading_only=settings.paper_trading_only,
        real_trading_enabled=settings.real_trading_enabled,
    )

    if args.market == "KR":
        snapshot = client.get_domestic_price(args.symbol, name=args.name)
        print(f"{snapshot.name} ({snapshot.symbol})")
        print("market=KR")
        print(f"price={snapshot.price:,.0f} KRW")
    else:
        snapshot = client.get_overseas_price(args.symbol, exchange=args.exchange, name=args.name)
        print(f"{snapshot.name} ({snapshot.symbol})")
        print("market=US")
        print(f"exchange={snapshot.exchange}")
        print(f"price=${snapshot.price:,.2f}")

    print(f"change_pct={snapshot.change_pct:+.2f}%")
    print(f"trading_value_krw={snapshot.trading_value_krw:,.0f}")
    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"order_enabled={settings.order_enabled}")
    print(f"real_trading_enabled={settings.real_trading_enabled}")


if __name__ == "__main__":
    main()
