import argparse

from app.brokers.kis_client import KisClient
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check KIS paper-account buying power.")
    parser.add_argument("market", choices=("KR", "US"))
    parser.add_argument("symbol")
    parser.add_argument("price", type=float)
    parser.add_argument("--exchange", default="NAS")
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
    result = client.get_buying_power(
        market=args.market,
        symbol=args.symbol,
        price=args.price,
        exchange=args.exchange,
    )

    decimals = 0 if result.currency == "KRW" else 2
    print("KIS paper buying power check.")
    print(f"market={result.market}")
    print(f"symbol={result.symbol}")
    print(f"available_amount={result.available_amount:,.{decimals}f} {result.currency}")
    print(f"available_quantity={result.available_quantity}")
    print("order_sent=False")


if __name__ == "__main__":
    main()
