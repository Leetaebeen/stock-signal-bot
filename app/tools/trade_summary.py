from app.config import get_settings
from app.trading.journal import TradeJournal


def main() -> None:
    settings = get_settings()
    journal = TradeJournal(settings.trade_journal_path)
    summary = journal.performance_summary()
    if not summary:
        print("completed_trades=0")
    else:
        for currency, item in summary.items():
            trades = int(item["trades"])
            wins = int(item["wins"])
            win_rate = (wins / trades * 100) if trades else 0.0
            print(
                f"{currency} trades={trades} wins={wins} win_rate={win_rate:.2f}% "
                f"realized_pnl={item['realized_pnl']:,.2f} "
                f"average_pnl_pct={item['average_pnl_pct']:+.2f}%"
            )

    signals = journal.signal_summary()
    print(
        "signals={observations} labeled_5m={labeled_5m} labeled_15m={labeled_15m} "
        "labeled_30m={labeled_30m} avg_5m={average_return_5m:+.2f}% "
        "avg_15m={average_return_15m:+.2f}% avg_30m={average_return_30m:+.2f}%".format(
            **signals
        )
    )
    readiness = journal.learning_readiness(settings.learning_min_labeled_samples)
    if not readiness:
        print(
            f"learning_ready=false labeled_samples=0 "
            f"required_samples={settings.learning_min_labeled_samples}"
        )
    for market, item in readiness.items():
        print(
            f"{market} learning_ready={str(item['ready']).lower()} "
            f"labeled_samples={item['labeled_samples']} "
            f"remaining_samples={item['remaining_samples']}"
        )


if __name__ == "__main__":
    main()
