from app.config import get_settings
from app.trading.journal import TradeJournal
from app.trading.state import JsonPositionStore


def main() -> None:
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


if __name__ == "__main__":
    main()
