import logging
import time
from datetime import datetime

from app.alerts.telegram import TelegramAlerter
from app.brokers.kis_client import KisClient
from app.config import Settings
from app.learning.pipeline import LearningPipeline
from app.scanners.momentum import (
    MomentumScanner,
    ScanCandidate,
    load_symbols_from_file,
    parse_exchange_map,
    parse_symbol_list,
)
from app.scanners.universe import DynamicUniverseProvider, parse_exchanges
from app.trading.calendar import MarketCalendar
from app.trading.executor import ExecutionConfig, ExecutionResult, TradingExecutor
from app.trading.journal import SignalRecord, TradeJournal
from app.trading.sessions import SessionPolicy, active_markets, market_closed_reason
from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, StrategyRules, evaluate_entry


logger = logging.getLogger(__name__)


class TradingRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rules = _rules_from_settings(settings)
        self.store = JsonPositionStore(settings.trading_state_path)
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
            rules=self.rules,
            exchange=settings.us_order_exchange,
            request_delay_seconds=settings.quote_request_delay_seconds,
        )
        self.universe = DynamicUniverseProvider(
            self.client,
            enabled=getattr(settings, "dynamic_universe_enabled", True),
            refresh_seconds=getattr(settings, "dynamic_universe_refresh_seconds", 300),
            kr_limit=getattr(settings, "dynamic_kr_symbol_limit", 20),
            us_limit_per_exchange=getattr(settings, "dynamic_us_symbol_limit_per_exchange", 10),
            us_exchanges=parse_exchanges(
                getattr(settings, "dynamic_us_exchanges", "NAS,NYS,AMS")
            ),
        )
        self.calendar = MarketCalendar(
            self.client,
            enabled=getattr(settings, "market_holiday_check_enabled", True),
            cache_seconds=getattr(settings, "market_holiday_cache_seconds", 21600),
        )
        self.journal = TradeJournal(settings.trade_journal_path)
        self.learning = LearningPipeline(settings, self.journal)
        self.executor = TradingExecutor(
            broker=self.client,
            store=self.store,
            rules=self.rules,
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
                auto_cancel_enabled=settings.order_auto_cancel_enabled,
                order_timeout_seconds=settings.order_timeout_seconds,
                cancel_max_attempts=settings.order_cancel_max_attempts,
                buying_power_check_enabled=settings.buying_power_check_enabled,
                max_entries_per_market_24h=settings.max_entries_per_market_24h,
                kr_max_realized_loss_24h_krw=settings.kr_max_realized_loss_24h_krw,
                us_max_realized_loss_24h_usd=settings.us_max_realized_loss_24h_usd,
                symbol_reentry_cooldown_seconds=settings.symbol_reentry_cooldown_seconds,
            ),
            alerter=TelegramAlerter(
                enabled=settings.telegram_enabled,
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
            ),
            journal=self.journal,
        )
        self.session_policy = SessionPolicy(
            allow_kr_regular=settings.allow_kr_regular_trading,
            allow_us_regular=settings.allow_us_regular_trading,
            allow_us_extended=settings.allow_us_extended_trading,
        )
        self._us_cursor = 0
        self._kr_cursor = 0
        self._last_holdings_sync = 0.0

    def run_once(self) -> list[ExecutionResult]:
        candidates = []
        now = datetime.now(KST)
        active = active_markets(self.session_policy, now=now, us_session=self.settings.us_order_session)
        active = [
            market
            for market in active
            if self.calendar.check(market, now).is_open
        ]
        try:
            self.learning.maybe_run(now)
        except Exception:
            logger.exception("daily learning evaluation failed")
        logger.info("scan cycle active_markets=%s", ",".join(active) if active else "NONE")
        results = self._sync_holdings_if_due()
        pending_results = self.executor.reconcile_pending_orders(cancel_markets=set(active))
        results.extend(pending_results)
        for result in pending_results:
            if result.action != "PENDING":
                logger.info(
                    "pending order result symbol=%s action=%s reason=%s order_no=%s",
                    result.symbol,
                    result.action,
                    result.reason,
                    result.order_no,
                )
        positions_at_cycle_start = set(self.store.load())
        results.extend(self._monitor_open_positions(active))
        pending_symbols = {item.symbol for item in self.store.load_pending_orders()}
        excluded_symbols = positions_at_cycle_start | set(self.store.load()) | pending_symbols
        us_symbols, us_exchange_map, us_name_map = (
            self._next_us_universe() if "US" in active else ([], {}, {})
        )
        kr_symbols = self._next_kr_universe() if "KR" in active else []
        if us_symbols:
            candidates.extend(
                self.scanner.scan_us(
                    [symbol for symbol in us_symbols if symbol not in excluded_symbols],
                    limit=self.settings.scan_candidate_limit,
                    exchange_by_symbol=us_exchange_map,
                    name_by_symbol=us_name_map,
                )
            )
        if kr_symbols:
            candidates.extend(
                self.scanner.scan_kr(
                    [symbol for symbol in kr_symbols if symbol not in excluded_symbols],
                    limit=self.settings.scan_candidate_limit,
                )
            )
        self._label_due_signals(active, candidates)
        if not candidates:
            logger.info("scan completed: no entry candidate")
            return results
        for candidate in sorted(candidates, key=lambda item: item.score, reverse=True)[: self.settings.scan_candidate_limit]:
            if not self._can_trade(candidate.signal.market):
                reason = market_closed_reason(candidate.signal.market, session=self.settings.us_order_session)
                logger.info("scan result symbol=%s action=SKIP reason=%s", candidate.signal.symbol, reason)
                result = ExecutionResult("SKIP", candidate.signal.symbol, reason)
                self._record_signal(candidate, result)
                results.append(result)
                continue
            result = self.executor.handle_signal(candidate.signal)
            logger.info("scan result symbol=%s action=%s reason=%s", result.symbol, result.action, result.reason)
            self._record_signal(candidate, result)
            results.append(result)
        return results

    def _record_signal(self, candidate: ScanCandidate, result: ExecutionResult) -> None:
        if not getattr(self.settings, "signal_journal_enabled", True):
            return
        signal = candidate.signal
        strategy = evaluate_entry(signal, self.rules)
        try:
            self.journal.record_signal(
                SignalRecord(
                    symbol=signal.symbol,
                    name=signal.name,
                    market=signal.market,
                    exchange=signal.exchange,
                    observed_at=signal.observed_at or datetime.now(KST),
                    price=signal.price,
                    change_pct=signal.change_pct,
                    volume_ratio=signal.volume_ratio,
                    trading_value_krw=signal.trading_value_krw,
                    one_minute_change_pct=signal.one_minute_change_pct,
                    five_minute_change_pct=signal.five_minute_change_pct,
                    breakout_pct=signal.breakout_pct,
                    vwap_extension_pct=signal.vwap_extension_pct,
                    confirmation_bars=signal.confirmation_bars,
                    score=candidate.score,
                    source=candidate.source,
                    strategy_action=strategy.action,
                    strategy_reason=strategy.reason,
                    execution_action=result.action,
                    execution_reason=result.reason,
                )
            )
        except Exception:
            logger.exception("signal journal write failed symbol=%s", signal.symbol)

    def _label_due_signals(
        self,
        active_markets_now: list[str],
        candidates: list[ScanCandidate],
    ) -> None:
        if not getattr(self.settings, "signal_journal_enabled", True):
            return
        active = {market.upper() for market in active_markets_now}
        if not active:
            return
        now = datetime.now(KST)
        tasks = self.journal.due_signal_labels(
            now,
            tolerance_seconds=getattr(self.settings, "signal_label_tolerance_seconds", 180),
            limit=50,
        )
        grouped = {}
        for task in tasks:
            if task.market.upper() not in active:
                continue
            grouped.setdefault((task.market.upper(), task.symbol, task.exchange), []).append(task)

        candidate_prices = {
            (item.signal.market.upper(), item.signal.symbol): item.signal.price
            for item in candidates
            if item.signal.price > 0
        }
        max_quotes = max(getattr(self.settings, "signal_label_max_quotes_per_cycle", 5), 0)
        quote_count = 0
        for (market, symbol, exchange), symbol_tasks in grouped.items():
            price = candidate_prices.get((market, symbol))
            if price is None:
                if quote_count >= max_quotes:
                    break
                if quote_count:
                    time.sleep(max(self.settings.quote_request_delay_seconds, 0))
                try:
                    if market == "KR":
                        price = self.client.get_domestic_price(symbol).price
                    else:
                        price = self.client.get_overseas_price(
                            symbol,
                            exchange=exchange or self.settings.us_order_exchange,
                        ).price
                except Exception as exc:
                    logger.warning("signal label quote skipped symbol=%s reason=%s", symbol, exc)
                    continue
                quote_count += 1
            for task in symbol_tasks:
                if self.journal.update_signal_label(task, current_price=price, labeled_at=now):
                    logger.info(
                        "signal labeled symbol=%s horizon=%sm price=%s",
                        symbol,
                        task.horizon_minutes,
                        price,
                    )

    def _sync_holdings_if_due(self) -> list[ExecutionResult]:
        now = time.monotonic()
        interval = max(getattr(self.settings, "account_sync_interval_seconds", 300), 30)
        if self._last_holdings_sync and now - self._last_holdings_sync < interval:
            return []

        results: list[ExecutionResult] = []
        successful_markets = 0
        for market in ("KR", "US"):
            try:
                market_results = self.executor.reconcile_holdings(market)
                results.extend(market_results)
                successful_markets += 1
                for result in market_results:
                    logger.warning(
                        "holding sync market=%s symbol=%s action=%s reason=%s",
                        market,
                        result.symbol,
                        result.action,
                        result.reason,
                    )
            except Exception as exc:
                logger.warning("holding sync failed market=%s reason=%s", market, exc)
        if successful_markets:
            self._last_holdings_sync = now
        return results

    def _monitor_open_positions(self, active_markets_now: list[str]) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        for position in self.store.load().values():
            if not position.managed and not position.liquidation_requested:
                continue
            if position.market.upper() not in active_markets_now:
                continue
            try:
                if position.market.upper() == "KR":
                    snapshot = self.client.get_domestic_price(position.symbol, name=position.name)
                else:
                    snapshot = self.client.get_overseas_price(
                        position.symbol,
                        exchange=position.exchange or self.settings.us_order_exchange,
                        name=position.name,
                    )
            except Exception as exc:
                logger.warning("position quote skipped symbol=%s reason=%s", position.symbol, exc)
                continue
            signal = MarketSignal(
                symbol=position.symbol,
                name=position.name,
                market=position.market,
                price=snapshot.price,
                change_pct=snapshot.change_pct,
                volume_ratio=0.0,
                trading_value_krw=snapshot.trading_value_krw,
                observed_at=datetime.now(KST),
                exchange=position.exchange or snapshot.exchange,
            )
            result = self.executor.handle_signal(signal)
            logger.info("position result symbol=%s action=%s reason=%s", result.symbol, result.action, result.reason)
            results.append(result)
        return results

    def _can_trade(self, market: str) -> bool:
        session = self.settings.us_order_session if market.upper() == "US" else "regular"
        now = datetime.now(KST)
        return (
            self.session_policy.is_market_open(market, now=now, session=session)
            and self.calendar.check(market, now).is_open
        )

    def _us_symbols(self) -> list[str]:
        symbols = parse_symbol_list(self.settings.us_scan_symbols)
        symbols.extend(load_symbols_from_file(self.settings.us_scan_symbols_path))
        return _dedupe(symbols)

    def _kr_symbols(self) -> list[str]:
        symbols = parse_symbol_list(self.settings.kr_scan_symbols)
        symbols.extend(load_symbols_from_file(self.settings.kr_scan_symbols_path))
        return _dedupe(symbols)

    def _us_exchange_map(self) -> dict[str, str]:
        return parse_exchange_map(self.settings.us_symbol_exchanges)

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

    def _next_us_universe(self) -> tuple[list[str], dict[str, str], dict[str, str]]:
        selection = self.universe.select_us(self._us_symbols(), self._us_exchange_map())
        symbols, self._us_cursor = _next_batch(
            selection.symbols,
            self._us_cursor,
            self.settings.us_scan_batch_size,
        )
        logger.info(
            "universe market=US source=%s symbols=%s",
            selection.source,
            len(symbols),
        )
        return symbols, selection.exchange_by_symbol, selection.name_by_symbol

    def _next_kr_universe(self) -> list[str]:
        selection = self.universe.select_kr(self._kr_symbols())
        symbols, self._kr_cursor = _next_batch(
            selection.symbols,
            self._kr_cursor,
            self.settings.kr_scan_batch_size,
        )
        logger.info(
            "universe market=KR source=%s symbols=%s",
            selection.source,
            len(symbols),
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
