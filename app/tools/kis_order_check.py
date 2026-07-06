import argparse

from app.brokers.kis_client import KisClient
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="KIS paper order payload/check tool.")
    parser.add_argument("market", choices=["KR", "US"])
    parser.add_argument("side", choices=["buy", "sell"])
    parser.add_argument("symbol")
    parser.add_argument("--qty", type=int, default=1)
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--exchange", default="NAS")
    parser.add_argument("--order-type", choices=["limit", "market"], default="limit")
    parser.add_argument("--session", choices=["regular", "day", "pre", "after"], default="regular")
    parser.add_argument("--execute", action="store_true")
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
    request = client.build_order_request(
        market=args.market,
        side=args.side,
        symbol=args.symbol,
        quantity=args.qty,
        price=args.price,
        exchange=args.exchange,
        order_type=args.order_type,
        session=args.session,
    )

    print("KIS paper order check.")
    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"order_enabled={settings.order_enabled}")
    print(f"execute={args.execute}")
    print(
        "request="
        f"{request.market} {request.side} {request.symbol} qty={request.quantity} "
        f"price={request.price:g} type={request.order_type} session={request.session}"
    )

    if not args.execute:
        print("dry_run=true")
        print("No order was sent.")
        return

    if request.market == "KR":
        result = client.place_domestic_order(
            side=request.side,
            symbol=request.symbol,
            quantity=request.quantity,
            price=int(request.price),
            order_type=request.order_type,
            order_enabled=settings.order_enabled,
            paper_trading_only=settings.paper_trading_only,
            real_trading_enabled=settings.real_trading_enabled,
        )
    else:
        result = client.place_overseas_order(
            side=request.side,
            symbol=request.symbol,
            quantity=request.quantity,
            price=request.price,
            exchange=request.exchange or args.exchange,
            order_type=request.order_type,
            session=request.session,
            order_enabled=settings.order_enabled,
            paper_trading_only=settings.paper_trading_only,
            real_trading_enabled=settings.real_trading_enabled,
        )

    print(f"order_sent=true order_no={result.order_no or '-'} message={result.message}")


if __name__ == "__main__":
    main()
