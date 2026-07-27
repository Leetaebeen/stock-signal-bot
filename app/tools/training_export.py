import argparse

from app.config import get_settings
from app.trading.journal import TradeJournal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/training_signals.csv")
    args = parser.parse_args()

    settings = get_settings()
    journal = TradeJournal(settings.trade_journal_path)
    rows = journal.export_training_dataset(args.output)
    print(f"training_rows={rows}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
