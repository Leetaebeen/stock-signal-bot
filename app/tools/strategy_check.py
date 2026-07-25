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
    parser.add_argument("--one-minute-change-pct", type=float, default=0.6)
    parser.add_argument("--five-minute-change-pct", type=float, default=1.8)
    parser.add_argument("--breakout-pct", type=float, default=0.5)
    parser.add_argument("--vwap-extension-pct", type=float, default=0.8)
    parser.add_argument("--confirmation-bars", type=int, default=12)
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
        one_minute_change_pct=args.one_minute_change_pct,
        five_minute_change_pct=args.five_minute_change_pct,
        breakout_pct=args.breakout_pct,
        vwap_extension_pct=args.vwap_extension_pct,
        confirmation_bars=args.confirmation_bars,
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
        entry_min_score=settings.entry_min_score,
        entry_min_confirmation_bars=settings.entry_min_confirmation_bars,
        entry_min_one_minute_change_pct=settings.entry_min_one_minute_change_pct,
        entry_max_one_minute_change_pct=settings.entry_max_one_minute_change_pct,
        entry_min_five_minute_change_pct=settings.entry_min_five_minute_change_pct,
        entry_max_five_minute_change_pct=settings.entry_max_five_minute_change_pct,
        entry_min_breakout_pct=settings.entry_min_breakout_pct,
        entry_max_vwap_extension_pct=settings.entry_max_vwap_extension_pct,
        take_profit_pct=settings.take_profit_pct,
        stop_loss_pct=settings.stop_loss_pct,
        trailing_start_pct=settings.trailing_start_pct,
        trailing_drawdown_pct=settings.trailing_drawdown_pct,
        max_hold_seconds=settings.max_hold_seconds,
    )


if __name__ == "__main__":
    main()
