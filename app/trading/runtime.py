import logging

from app.alerts.telegram import TelegramAlerter
from app.brokers.kis_client import KisClient
from app.config import Settings
from app.scanners.momentum import MomentumScanner, TradingValueBaseline, load_symbols_from_file, parse_symbol_list
from app.trading.executor import ExecutionConfig, ExecutionResult, TradingExecutor
from app.trading.state import JsonPositionStore
from app.trading.strategy import StrategyRules


logger = logging.getLogger(__name__)


class TradingRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = KisClient(
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
            account_no=settings.kis_account_no,
            account_product_code=settings.kis_account_product_code,
            env=settings.kis_env,
            token_cache_path=settings.kis_token_cache_path,
        )
        self.scanner = MomentumScanner(
            quote_client=self.client,
            baseline=TradingValueBaseline(),
            exchange=settings.us_order_exchange,
            request_delay_seconds=settings.quote_request_delay_seconds,
        )
        self.executor = TradingExecutor(
            broker=self.client,
            store=JsonPositionStore(settings.trading_state_path),
            rules=_rules_from_settings(settings),
            config=ExecutionConfig(
                quantity=settings.trading_default_quantity,
                order_enabled=settings.order_enabled,
                paper_trading_only=settings.paper_trading_only,
                real_trading_enabled=settings.real_trading_enabled,
                exchange=settings.us_order_exchange,
                session=settings.us_order_session,
                notify_trades=settings.telegram_notify_trades,
                notify_errors=settings.telegram_notify_errors,
            ),
            alerter=TelegramAlerter(
                enabled=settings.telegram_enabled,
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
            ),
        )

    def run_once(self) -> list[ExecutionResult]:
        symbols = self._symbols()
        if not symbols:
            logger.info("scan skipped: no symbols configured")
            return []
        candidates = self.scanner.scan_us(symbols, limit=self.settings.scan_candidate_limit)
        results: list[ExecutionResult] = []
        for candidate in candidates:
            result = self.executor.handle_signal(candidate.signal)
            logger.info("scan result symbol=%s action=%s reason=%s", result.symbol, result.action, result.reason)
            results.append(result)
        return results

    def _symbols(self) -> list[str]:
        symbols = parse_symbol_list(self.settings.us_scan_symbols)
        symbols.extend(load_symbols_from_file(self.settings.us_scan_symbols_path))
        deduped: list[str] = []
        for symbol in symbols:
            if symbol not in deduped:
                deduped.append(symbol)
        return deduped


def _rules_from_settings(settings: Settings) -> StrategyRules:
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
