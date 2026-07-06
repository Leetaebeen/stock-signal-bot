import argparse
from datetime import datetime

from app.config import get_settings
from app.trading.strategy import KST, MarketSignal, StrategyRules, evaluate_entry, evaluate_exit, open_position


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading strategy decision check tool.")
    parser.add_argument("symbol")
    parser.add_argument("--name", default=None)
    parser.add_argument("--market", choices=["KR", "US"], default="US")
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--change-pct", type=float, required=True)
    parser.add_argument("--volume-ratio", type=float, required=True)
    parser.add_argument("--trading-value-krw", type=float, required=True)
    parser.add_argument("--exit-price", type=float, default=None)
    args = parser.parse_args()

    settings = get_settings()
    rules = _rules_from_settings(settings)
    signal = MarketSignal(
        symbol=args.symbol.upper(),
        name=args.name or args.symbol.upper(),
        market=args.market,
        price=args.price,
        change_pct=args.change_pct,
        volume_ratio=args.volume_ratio,
        trading_value_krw=args.trading_value_krw,
        observed_at=datetime.now(KST),
    )

    entry = evaluate_entry(signal, rules)
    print(f"entry_action={entry.action}")
    print(f"entry_score={entry.score}")
    print(f"entry_reason={entry.reason}")

    if args.exit_price is not None:
        position = open_position(signal, quantity=settings.trading_default_quantity)
        exit_decision = evaluate_exit(position, current_price=args.exit_price, rules=rules)
        print(f"exit_action={exit_decision.action}")
        print(f"exit_reason={exit_decision.reason}")


def _rules_from_settings(settings) -> StrategyRules:
    return StrategyRules(
        entry_min_change_pct=settings.entry_min_change_pct,
        entry_max_change_pct=settings.entry_max_change_pct,
        entry_min_volume_ratio=settings.entry_min_volume_ratio,
        entry_max_volume_ratio=settings.entry_max_volume_ratio,
        entry_min_trading_value_krw=settings.entry_min_trading_value_krw,
        take_profit_pct=settings.take_profit_pct,
        stop_loss_pct=settings.stop_loss_pct,
        trailing_start_pct=settings.trailing_start_pct,
        trailing_drawdown_pct=settings.trailing_drawdown_pct,
        max_hold_seconds=settings.max_hold_seconds,
    )


if __name__ == "__main__":
    main()
