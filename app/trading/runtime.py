import logging

from app.alerts.telegram import TelegramAlerter
from app.brokers.kis_client import KisClient
from app.config import Settings
from app.scanners.momentum import MomentumScanner, TradingValueBaseline, load_symbols_from_file, parse_symbol_list
from app.trading.executor import ExecutionConfig, ExecutionResult, TradingExecutor
from app.trading.sessions import SessionPolicy, active_markets, market_closed_reason
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
                max_open_positions=settings.trading_max_open_positions,
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
        self.session_policy = SessionPolicy(
            allow_kr_regular=settings.allow_kr_regular_trading,
            allow_us_regular=settings.allow_us_regular_trading,
            allow_us_extended=settings.allow_us_extended_trading,
        )
        self._us_cursor = 0
        self._kr_cursor = 0

    def run_once(self) -> list[ExecutionResult]:
        candidates = []
        active = active_markets(self.session_policy, us_session=self.settings.us_order_session)
        logger.info("scan cycle active_markets=%s", ",".join(active) if active else "NONE")
        us_symbols = self._next_us_symbols() if "US" in active else []
        kr_symbols = self._next_kr_symbols() if "KR" in active else []
        if us_symbols:
            candidates.extend(self.scanner.scan_us(us_symbols, limit=self.settings.scan_candidate_limit))
        if kr_symbols:
            candidates.extend(self.scanner.scan_kr(kr_symbols, limit=self.settings.scan_candidate_limit))
        if not candidates:
            logger.info("scan skipped: no open market or no symbols configured")
            return []
        results: list[ExecutionResult] = []
        for candidate in sorted(candidates, key=lambda item: item.score, reverse=True)[: self.settings.scan_candidate_limit]:
            if not self._can_trade(candidate.signal.market):
                reason = market_closed_reason(candidate.signal.market, session=self.settings.us_order_session)
                logger.info("scan result symbol=%s action=SKIP reason=%s", candidate.signal.symbol, reason)
                results.append(ExecutionResult("SKIP", candidate.signal.symbol, reason))
                continue
            result = self.executor.handle_signal(candidate.signal)
            logger.info("scan result symbol=%s action=%s reason=%s", result.symbol, result.action, result.reason)
            results.append(result)
        return results

    def _can_trade(self, market: str) -> bool:
        session = self.settings.us_order_session if market.upper() == "US" else "regular"
        return self.session_policy.is_market_open(market, session=session)

    def _us_symbols(self) -> list[str]:
        symbols = parse_symbol_list(self.settings.us_scan_symbols)
        symbols.extend(load_symbols_from_file(self.settings.us_scan_symbols_path))
        return _dedupe(symbols)

    def _kr_symbols(self) -> list[str]:
        symbols = parse_symbol_list(self.settings.kr_scan_symbols)
        symbols.extend(load_symbols_from_file(self.settings.kr_scan_symbols_path))
        return _dedupe(symbols)

    def _next_us_symbols(self) -> list[str]:
        symbols, self._us_cursor = _next_batch(
            self._us_symbols(),
            self._us_cursor,
            self.settings.us_scan_batch_size,
        )
        return symbols

    def _next_kr_symbols(self) -> list[str]:
        symbols, self._kr_cursor = _next_batch(
            self._kr_symbols(),
            self._kr_cursor,
            self.settings.kr_scan_batch_size,
        )
        return symbols


def _dedupe(symbols: list[str]) -> list[str]:
    deduped: list[str] = []
    for symbol in symbols:
        if symbol not in deduped:
            deduped.append(symbol)
    return deduped


def _next_batch(symbols: list[str], cursor: int, batch_size: int) -> tuple[list[str], int]:
    if not symbols:
        return [], 0
    if batch_size <= 0 or batch_size >= len(symbols):
        return symbols, 0

    start = cursor % len(symbols)
    end = start + batch_size
    if end <= len(symbols):
        batch = symbols[start:end]
    else:
        batch = symbols[start:] + symbols[: end - len(symbols)]
    return batch, end % len(symbols)


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
