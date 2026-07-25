from app.config import get_settings
from app.trading.journal import TradeJournal


def main() -> None:
    settings = get_settings()
    summary = TradeJournal(settings.trade_journal_path).performance_summary()
    if not summary:
        print("completed_trades=0")
        return
    for currency, item in summary.items():
        trades = int(item["trades"])
        wins = int(item["wins"])
        win_rate = (wins / trades * 100) if trades else 0.0
        print(
            f"{currency} trades={trades} wins={wins} win_rate={win_rate:.2f}% "
            f"realized_pnl={item['realized_pnl']:,.2f} "
            f"average_pnl_pct={item['average_pnl_pct']:+.2f}%"
        )


if __name__ == "__main__":
    main()
