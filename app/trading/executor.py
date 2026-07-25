import logging
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from app.alerts.telegram import TelegramAlerter
from app.alerts.trade_messages import OrderFailure, TradeFill, build_order_failure_message, build_trade_fill_message
from app.brokers.kis_client import BrokerHolding, CancelResult, OrderFillStatus, OrderResult
from app.trading.journal import FillRecord, TradeJournal
from app.trading.state import JsonPositionStore, PendingOrder
from app.trading.strategy import (
    KST,
    MarketSignal,
    Position,
    StrategyRules,
    TradeDecision,
    evaluate_entry,
    evaluate_exit,
    open_position,
)


logger = logging.getLogger(__name__)


class TradingBroker(Protocol):
    def place_domestic_order(
        self,
        *,
        side: str,
        symbol: str,
        quantity: int,
        price: int,
        order_type: str = "limit",
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> OrderResult:
        ...

    def place_overseas_order(
        self,
        *,
        side: str,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str = "NAS",
        order_type: str = "limit",
        session: str = "regular",
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> OrderResult:
        ...

    def get_order_fill_status(
        self,
        *,
        market: str,
        order_no: str,
        symbol: str,
        quantity: float,
        submitted_at: datetime,
    ) -> OrderFillStatus:
        ...

    def get_holdings(self, market: str) -> list[BrokerHolding]:
        ...

    def cancel_order(
        self,
        *,
        market: str,
        symbol: str,
        order_no: str,
        quantity: int,
        requested_price: float,
        order_org_no: str | None = None,
        exchange: str | None = None,
        session: str = "regular",
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> CancelResult:
        ...


@dataclass(frozen=True)
class ExecutionConfig:
    quantity: int
    order_enabled: bool
    paper_trading_only: bool
    real_trading_enabled: bool
    max_open_positions: int = 1
    exchange: str = "NAS"
    session: str = "regular"
    order_type: str = "limit"
    notify_trades: bool = True
    notify_errors: bool = True
    auto_cancel_enabled: bool = True
    order_timeout_seconds: int = 120
    cancel_max_attempts: int = 3


@dataclass(frozen=True)
class ExecutionResult:
    action: str
    symbol: str
    reason: str
    order_no: str | None = None


class TradingExecutor:
    def __init__(
        self,
        *,
        broker: TradingBroker,
        store: JsonPositionStore,
        rules: StrategyRules,
        config: ExecutionConfig,
        alerter: TelegramAlerter | None = None,
        journal: TradeJournal | None = None,
    ) -> None:
        self.broker = broker
        self.store = store
        self.rules = rules
        self.config = config
        self.alerter = alerter
        self.journal = journal

    def handle_signal(self, signal: MarketSignal) -> ExecutionResult:
        pending = self.store.pending_for_symbol(signal.symbol)
        if pending:
            return ExecutionResult("PENDING", signal.symbol, f"주문 체결 대기: {pending.side}", pending.order_no)
        positions = self.store.load()
        position = positions.get(signal.symbol)
        if position:
            return self._handle_existing_position(signal, position, positions)
        return self._handle_entry(signal, positions)

    def _handle_entry(self, signal: MarketSignal, positions: dict[str, Position]) -> ExecutionResult:
        decision = evaluate_entry(signal, self.rules)
        if not decision.should_buy:
            return ExecutionResult("HOLD", signal.symbol, decision.reason)
        pending_buys = sum(1 for item in self.store.load_pending_orders() if item.side.lower() == "buy")
        if self.config.max_open_positions > 0 and len(positions) + pending_buys >= self.config.max_open_positions:
            return ExecutionResult(
                "HOLD",
                signal.symbol,
                f"최대 보유·매수대기 종목 수 도달: {len(positions) + pending_buys}/{self.config.max_open_positions}",
            )

        try:
            order = self._place_order(
                side="buy",
                signal=signal,
                quantity=self.config.quantity,
                price=signal.price,
            )
        except Exception as exc:
            self._notify_failure(signal, "BUY", str(exc))
            return ExecutionResult("ERROR", signal.symbol, str(exc))

        if not order.order_no:
            reason = "KIS 주문 응답에 주문번호가 없습니다."
            self._notify_failure(signal, "BUY", reason)
            return ExecutionResult("ERROR", signal.symbol, reason)
        self.store.add_pending_order(
            PendingOrder(
                order_no=order.order_no,
                market=signal.market,
                side="buy",
                symbol=signal.symbol,
                name=signal.name,
                quantity=self.config.quantity,
                requested_price=signal.price,
                submitted_at=signal.observed_at or datetime.now(KST),
                reason=decision.reason,
                exchange=signal.exchange,
                session=order.session,
                order_org_no=order.order_org_no,
            )
        )
        return ExecutionResult("SUBMITTED", signal.symbol, decision.reason, order_no=order.order_no)

    def _handle_existing_position(
        self,
        signal: MarketSignal,
        position: Position,
        positions: dict[str, Position],
    ) -> ExecutionResult:
        updated = position.with_price(signal.price)
        decision = (
            TradeDecision("SELL", "사용자 요청 모의 포지션 정리")
            if updated.liquidation_requested
            else evaluate_exit(updated, current_price=signal.price, now=signal.observed_at, rules=self.rules)
        )
        if not decision.should_sell:
            positions[signal.symbol] = updated
            self.store.save(positions)
            return ExecutionResult("HOLD", signal.symbol, decision.reason)

        try:
            order = self._place_order(
                side="sell",
                signal=signal,
                quantity=int(updated.quantity),
                price=signal.price,
            )
        except Exception as exc:
            self._notify_failure(signal, "SELL", str(exc))
            return ExecutionResult("ERROR", signal.symbol, str(exc))

        if not order.order_no:
            reason = "KIS 주문 응답에 주문번호가 없습니다."
            self._notify_failure(signal, "SELL", reason)
            return ExecutionResult("ERROR", signal.symbol, reason)
        positions[signal.symbol] = updated
        self.store.save(positions)
        self.store.add_pending_order(
            PendingOrder(
                order_no=order.order_no,
                market=signal.market,
                side="sell",
                symbol=signal.symbol,
                name=signal.name,
                quantity=updated.quantity,
                requested_price=signal.price,
                submitted_at=signal.observed_at or datetime.now(KST),
                reason=decision.reason,
                exchange=signal.exchange or updated.exchange,
                session=order.session,
                order_org_no=order.order_org_no,
            )
        )
        return ExecutionResult("SUBMITTED", signal.symbol, decision.reason, order_no=order.order_no)

    def reconcile_pending_orders(
        self,
        cancel_markets: set[str] | None = None,
    ) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        for pending in self.store.load_pending_orders():
            try:
                status = self.broker.get_order_fill_status(
                    market=pending.market,
                    order_no=pending.order_no,
                    symbol=pending.symbol,
                    quantity=pending.quantity,
                    submitted_at=pending.submitted_at,
                )
            except Exception as exc:
                logger.warning(
                    "fill inquiry failed order_no=%s symbol=%s reason=%s",
                    pending.order_no,
                    pending.symbol,
                    exc,
                )
                results.append(ExecutionResult("PENDING", pending.symbol, str(exc), pending.order_no))
                continue

            if status.state == "FILLED":
                results.append(self._apply_confirmed_fill(pending, status))
            elif status.state == "PARTIAL_CANCELED":
                results.append(self._apply_confirmed_fill(pending, status, partial=True))
            elif status.state in {"CANCELED", "REJECTED"}:
                self.store.remove_pending_order(pending.order_no)
                reason = f"주문 {status.state.lower()}"
                if status.state == "REJECTED":
                    self._notify_failure(_pending_to_signal(pending), pending.side.upper(), reason)
                results.append(ExecutionResult(status.state, pending.symbol, reason, pending.order_no))
            elif (
                cancel_markets is None
                or pending.market.strip().upper() in cancel_markets
            ) and self._should_cancel(pending, status):
                results.append(self._request_cancel(pending, status))
            else:
                results.append(
                    ExecutionResult(status.state, pending.symbol, "체결 확인 대기", pending.order_no)
                )
        return results

    def _should_cancel(self, pending: PendingOrder, status: OrderFillStatus) -> bool:
        if not self.config.auto_cancel_enabled or self.config.order_timeout_seconds <= 0:
            return False
        if pending.cancel_attempts >= self.config.cancel_max_attempts:
            return False
        if status.state not in {"PENDING", "PARTIAL", "UNKNOWN"}:
            return False
        reference_time = pending.cancel_requested_at or pending.submitted_at
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=KST)
        age_seconds = (datetime.now(KST) - reference_time.astimezone(KST)).total_seconds()
        return age_seconds >= self.config.order_timeout_seconds

    def _request_cancel(
        self,
        pending: PendingOrder,
        status: OrderFillStatus,
    ) -> ExecutionResult:
        order_org_no = pending.order_org_no or str(
            status.raw.get("ord_gno_brno")
            or status.raw.get("krx_fwdg_ord_orgno")
            or ""
        )
        remaining_quantity = max(int(pending.quantity - status.filled_quantity), 1)
        try:
            self.broker.cancel_order(
                market=pending.market,
                symbol=pending.symbol,
                order_no=pending.order_no,
                quantity=remaining_quantity,
                requested_price=pending.requested_price,
                order_org_no=order_org_no or None,
                exchange=pending.exchange,
                session=pending.session,
                order_enabled=self.config.order_enabled,
                paper_trading_only=self.config.paper_trading_only,
                real_trading_enabled=self.config.real_trading_enabled,
            )
        except Exception as exc:
            self.store.add_pending_order(
                replace(
                    pending,
                    order_org_no=order_org_no or pending.order_org_no,
                    cancel_requested_at=datetime.now(KST),
                    cancel_attempts=pending.cancel_attempts + 1,
                )
            )
            logger.warning(
                "cancellation failed order_no=%s symbol=%s reason=%s",
                pending.order_no,
                pending.symbol,
                exc,
            )
            return ExecutionResult("PENDING", pending.symbol, f"취소 요청 실패: {exc}", pending.order_no)

        self.store.add_pending_order(
            replace(
                pending,
                order_org_no=order_org_no or pending.order_org_no,
                cancel_requested_at=datetime.now(KST),
                cancel_attempts=pending.cancel_attempts + 1,
            )
        )
        return ExecutionResult("CANCEL_SUBMITTED", pending.symbol, "미체결 주문 자동 취소 요청", pending.order_no)

    def reconcile_holdings(self, market: str) -> list[ExecutionResult]:
        holdings = self.broker.get_holdings(market)
        account = {item.symbol: item for item in holdings}
        positions = self.store.load()
        pending_symbols = {item.symbol for item in self.store.load_pending_orders()}
        results: list[ExecutionResult] = []

        for symbol, holding in account.items():
            if symbol in pending_symbols:
                continue
            existing = positions.get(symbol)
            entry_price = holding.average_price or holding.current_price
            if entry_price <= 0:
                logger.warning("holding sync skipped zero price market=%s symbol=%s", market, symbol)
                continue
            if existing:
                positions[symbol] = Position(
                    symbol=symbol,
                    name=holding.name or existing.name,
                    market=holding.market,
                    quantity=holding.quantity,
                    entry_price=entry_price,
                    entry_at=existing.entry_at,
                    highest_price=max(existing.highest_price, holding.current_price, entry_price),
                    exchange=holding.exchange or existing.exchange,
                    managed=existing.managed,
                    liquidation_requested=existing.liquidation_requested,
                )
                continue
            positions[symbol] = Position(
                symbol=symbol,
                name=holding.name,
                market=holding.market,
                quantity=holding.quantity,
                entry_price=entry_price,
                entry_at=datetime.now(KST),
                highest_price=max(holding.current_price, entry_price),
                exchange=holding.exchange,
                managed=False,
                liquidation_requested=False,
            )
            results.append(ExecutionResult("SYNCED", symbol, "미추적 계좌 보유 종목을 관리 제외로 반영"))

        normalized_market = market.strip().upper()
        for symbol, position in list(positions.items()):
            if position.market.upper() != normalized_market or symbol in pending_symbols:
                continue
            if symbol not in account:
                positions.pop(symbol)
                results.append(ExecutionResult("REMOVED", symbol, "계좌에 없는 로컬 포지션 제거"))

        self.store.save(positions)
        return results

    def _apply_confirmed_fill(
        self,
        pending: PendingOrder,
        status: OrderFillStatus,
        *,
        partial: bool = False,
    ) -> ExecutionResult:
        fill_price = status.average_price or pending.requested_price
        fill_quantity = status.filled_quantity or pending.quantity
        filled_at = datetime.now(KST)
        positions = self.store.load()
        remaining_orders = [
            item for item in self.store.load_pending_orders() if item.order_no != pending.order_no
        ]

        if pending.side.lower() == "buy":
            signal = _pending_to_signal(pending, price=fill_price, observed_at=filled_at)
            positions[pending.symbol] = open_position(signal, quantity=fill_quantity, entry_at=filled_at)
            self.store.save_state(positions, remaining_orders)
            self._record_fill(
                FillRecord(
                    order_no=pending.order_no,
                    symbol=pending.symbol,
                    name=pending.name,
                    market=pending.market,
                    side="BUY",
                    quantity=fill_quantity,
                    price=fill_price,
                    currency=_currency_for_market(pending.market),
                    reason=pending.reason,
                    filled_at=filled_at,
                )
            )
            self._notify_fill(
                TradeFill(
                    symbol=pending.symbol,
                    name=pending.name,
                    market=pending.market,
                    side="BUY",
                    quantity=fill_quantity,
                    price=fill_price,
                    currency=_currency_for_market(pending.market),
                    reason=pending.reason,
                    filled_at=filled_at,
                )
            )
            action = "BUY_PARTIAL" if partial else "BUY"
        else:
            position = positions.get(pending.symbol)
            if partial and position and position.quantity > fill_quantity:
                positions[pending.symbol] = replace(position, quantity=position.quantity - fill_quantity)
            else:
                positions.pop(pending.symbol, None)
            self.store.save_state(positions, remaining_orders)
            holding_seconds = (
                int((filled_at - position.entry_at).total_seconds()) if position is not None else None
            )
            self._record_fill(
                FillRecord(
                    order_no=pending.order_no,
                    symbol=pending.symbol,
                    name=pending.name,
                    market=pending.market,
                    side="SELL",
                    quantity=fill_quantity,
                    price=fill_price,
                    entry_price=position.entry_price if position else None,
                    currency=_currency_for_market(pending.market),
                    reason=pending.reason,
                    filled_at=filled_at,
                )
            )
            self._notify_fill(
                TradeFill(
                    symbol=pending.symbol,
                    name=pending.name,
                    market=pending.market,
                    side="SELL",
                    quantity=fill_quantity,
                    price=fill_price,
                    entry_price=position.entry_price if position else None,
                    currency=_currency_for_market(pending.market),
                    reason=pending.reason,
                    holding_seconds=holding_seconds,
                    filled_at=filled_at,
                )
            )
            action = "SELL_PARTIAL" if partial else "SELL"

        return ExecutionResult(action, pending.symbol, pending.reason, pending.order_no)

    def _place_order(self, *, side: str, signal: MarketSignal, quantity: int, price: float) -> OrderResult:
        if signal.market.upper() == "KR":
            return self.broker.place_domestic_order(
                side=side,
                symbol=signal.symbol,
                quantity=quantity,
                price=int(price),
                order_type=self.config.order_type,
                order_enabled=self.config.order_enabled,
                paper_trading_only=self.config.paper_trading_only,
                real_trading_enabled=self.config.real_trading_enabled,
            )
        return self.broker.place_overseas_order(
            side=side,
            symbol=signal.symbol,
            quantity=quantity,
            price=price,
            exchange=signal.exchange or self.config.exchange,
            order_type=self.config.order_type,
            session=self.config.session,
            order_enabled=self.config.order_enabled,
            paper_trading_only=self.config.paper_trading_only,
            real_trading_enabled=self.config.real_trading_enabled,
        )

    def _record_fill(self, fill: FillRecord) -> None:
        if not self.journal:
            return
        try:
            self.journal.record_fill(fill)
        except Exception:
            logger.exception("trade journal write failed order_no=%s symbol=%s", fill.order_no, fill.symbol)

    def _notify_fill(self, fill: TradeFill) -> None:
        if self.alerter and self.config.notify_trades:
            self.alerter.send(build_trade_fill_message(fill))

    def _notify_failure(self, signal: MarketSignal, side: str, reason: str) -> None:
        if self.alerter and self.config.notify_errors:
            self.alerter.send(
                build_order_failure_message(
                    OrderFailure(
                        symbol=signal.symbol,
                        name=signal.name,
                        market=signal.market,
                        side=side,
                        reason=reason,
                        failed_at=signal.observed_at,
                    )
                )
            )


def _currency_for_market(market: str) -> str:
    return "KRW" if market.upper() == "KR" else "USD"


def _pending_to_signal(
    pending: PendingOrder,
    *,
    price: float | None = None,
    observed_at: datetime | None = None,
) -> MarketSignal:
    return MarketSignal(
        symbol=pending.symbol,
        name=pending.name,
        market=pending.market,
        price=price or pending.requested_price,
        change_pct=0.0,
        volume_ratio=0.0,
        trading_value_krw=0.0,
        observed_at=observed_at or pending.submitted_at,
        exchange=pending.exchange,
    )
