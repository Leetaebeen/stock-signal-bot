import argparse
from datetime import datetime

from app.alerts.telegram import TelegramAlerter
from app.brokers.kis_client import KisClient
from app.config import get_settings
from app.trading.executor import ExecutionConfig, TradingExecutor
from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, StrategyRules, evaluate_entry


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one strategy signal through the paper trading executor.")
    parser.add_argument("symbol")
    parser.add_argument("--name", default=None)
    parser.add_argument("--market", choices=["US"], default="US")
    parser.add_argument("--price", type=float, required=True)
    parser.add_argument("--change-pct", type=float, required=True)
    parser.add_argument("--volume-ratio", type=float, required=True)
    parser.add_argument("--trading-value-krw", type=float, required=True)
    parser.add_argument("--exchange", default="NAS")
    parser.add_argument("--session", choices=["regular", "day", "pre", "after"], default="regular")
    parser.add_argument("--execute", action="store_true")
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

    decision = evaluate_entry(signal, rules)
    print("paper trading signal check.")
    print(f"symbol={signal.symbol}")
    print(f"entry_action={decision.action}")
    print(f"entry_score={decision.score}")
    print(f"entry_reason={decision.reason}")
    print(f"execute={args.execute}")
    print(f"order_enabled={settings.order_enabled}")

    if not args.execute:
        print("dry_run=true")
        print("No order was sent.")
        return

    executor = TradingExecutor(
        broker=KisClient(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.kis_account_no,
            account_product_code=settings.kis_account_product_code,
            env=settings.kis_env,
            token_cache_path=settings.kis_token_cache_path,
        ),
        store=JsonPositionStore(settings.trading_state_path),
        rules=rules,
        config=ExecutionConfig(
            quantity=settings.trading_default_quantity,
            order_enabled=settings.order_enabled,
            paper_trading_only=settings.paper_trading_only,
            real_trading_enabled=settings.real_trading_enabled,
            exchange=args.exchange,
            session=args.session,
            notify_trades=settings.telegram_notify_trades,
            notify_errors=settings.telegram_notify_errors,
        ),
        alerter=TelegramAlerter(
            enabled=settings.telegram_enabled,
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
        ),
    )
    result = executor.handle_signal(signal)
    print(f"execution_action={result.action}")
    print(f"execution_reason={result.reason}")
    print(f"order_no={result.order_no or '-'}")


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
