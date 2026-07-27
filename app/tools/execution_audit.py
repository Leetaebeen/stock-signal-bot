import argparse

from app.brokers.kis_client import KisClient
from app.config import get_settings
from app.trading.journal import TradeJournal
from app.trading.state import JsonPositionStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--broker",
        action="store_true",
        help="KIS 체결 원장에서 미체결 주문 상태를 읽기 전용으로 확인합니다.",
    )
    args = parser.parse_args()
    settings = get_settings()
    store = JsonPositionStore(settings.trading_state_path)
    journal = TradeJournal(settings.trade_journal_path)
    positions = store.load()
    pending = store.load_pending_orders()
    fills = journal.fill_summary()

    print("execution_audit")
    print(f"positions={len(positions)} pending_orders={len(pending)}")
    for market in ("KR", "US"):
        item = fills.get(market, {"buys": 0, "sells": 0})
        print(f"{market} buy_fills={item['buys']} sell_fills={item['sells']}")
    for position in positions.values():
        state = "liquidation_requested" if position.liquidation_requested else (
            "managed" if position.managed else "observed"
        )
        print(
            f"position market={position.market} symbol={position.symbol} "
            f"quantity={position.quantity:g} state={state}"
        )
    for order in pending:
        print(
            f"pending market={order.market} side={order.side} symbol={order.symbol} "
            f"quantity={order.quantity:g} order_no={order.order_no}"
        )
    if args.broker and pending:
        client = KisClient(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.kis_account_no,
            account_product_code=settings.kis_account_product_code,
            env=settings.kis_env,
            token_cache_path=settings.kis_token_cache_path,
        )
        for order in pending:
            try:
                status = client.get_order_fill_status(
                    market=order.market,
                    order_no=order.order_no,
                    symbol=order.symbol,
                    quantity=order.quantity,
                    submitted_at=order.submitted_at,
                )
                print(
                    f"broker order_no={order.order_no} state={status.state} "
                    f"filled_quantity={status.filled_quantity:g} "
                    f"average_price={status.average_price:g}"
                )
            except Exception as exc:
                print(f"broker order_no={order.order_no} state=ERROR reason={exc}")


if __name__ == "__main__":
    main()
