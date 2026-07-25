from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.alerts.telegram import TelegramAlerter
from app.alerts.trade_messages import OrderFailure, TradeFill, build_order_failure_message, build_trade_fill_message
from app.brokers.kis_client import OrderResult
from app.trading.state import JsonPositionStore
from app.trading.strategy import KST, MarketSignal, Position, StrategyRules, evaluate_entry, evaluate_exit, open_position


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
    ) -> None:
        self.broker = broker
        self.store = store
        self.rules = rules
        self.config = config
        self.alerter = alerter

    def handle_signal(self, signal: MarketSignal) -> ExecutionResult:
        positions = self.store.load()
        position = positions.get(signal.symbol)
        if position:
            return self._handle_existing_position(signal, position, positions)
        return self._handle_entry(signal, positions)

    def _handle_entry(self, signal: MarketSignal, positions: dict[str, Position]) -> ExecutionResult:
        decision = evaluate_entry(signal, self.rules)
        if not decision.should_buy:
            return ExecutionResult("HOLD", signal.symbol, decision.reason)
        if self.config.max_open_positions > 0 and len(positions) >= self.config.max_open_positions:
            return ExecutionResult(
                "HOLD",
                signal.symbol,
                f"최대 보유 종목 수 도달: {len(positions)}/{self.config.max_open_positions}",
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

        position = open_position(signal, quantity=self.config.quantity, entry_at=signal.observed_at or datetime.now(KST))
        positions[signal.symbol] = position
        self.store.save(positions)
        self._notify_fill(
            TradeFill(
                symbol=signal.symbol,
                name=signal.name,
                market=signal.market,
                side="BUY",
                quantity=self.config.quantity,
                price=signal.price,
                currency=_currency_for_market(signal.market),
                reason=decision.reason,
                filled_at=signal.observed_at,
            )
        )
        return ExecutionResult("BUY", signal.symbol, decision.reason, order_no=order.order_no)

    def _handle_existing_position(
        self,
        signal: MarketSignal,
        position: Position,
        positions: dict[str, Position],
    ) -> ExecutionResult:
        updated = position.with_price(signal.price)
        decision = evaluate_exit(updated, current_price=signal.price, now=signal.observed_at, rules=self.rules)
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

        positions.pop(signal.symbol, None)
        self.store.save(positions)
        holding_seconds = int(((signal.observed_at or datetime.now(KST)) - updated.entry_at).total_seconds())
        self._notify_fill(
            TradeFill(
                symbol=signal.symbol,
                name=signal.name,
                market=signal.market,
                side="SELL",
                quantity=updated.quantity,
                price=signal.price,
                entry_price=updated.entry_price,
                currency=_currency_for_market(signal.market),
                reason=decision.reason,
                holding_seconds=holding_seconds,
                filled_at=signal.observed_at,
            )
        )
        return ExecutionResult("SELL", signal.symbol, decision.reason, order_no=order.order_no)

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
