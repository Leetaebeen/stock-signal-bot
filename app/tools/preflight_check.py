from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.brokers.kis_client import KisClient, summarize_domestic_balance
from app.config import Settings, get_settings
from app.scanners.momentum import MomentumScanner, load_symbols_from_file, parse_exchange_map, parse_symbol_list
from app.trading.runtime import _rules_from_settings
from app.trading.sessions import KST, SessionPolicy, active_markets, market_closed_reason


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str


def main() -> None:
    settings = get_settings()
    results = run_preflight(settings)

    print("preflight_check")
    for result in results:
        print(f"[{result.status}] {result.name}: {result.message}")

    if any(result.status == "FAIL" for result in results):
        raise SystemExit(1)


def run_preflight(settings: Settings) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_check_config(settings))
    results.append(_check_state_path(settings.trading_state_path))

    client = _build_client(settings)
    results.append(_check_kis_token(client))
    results.append(_check_domestic_balance(client))
    results.append(_check_sessions(settings))
    results.append(_check_scanner(settings, client))
    return results


def _check_config(settings: Settings) -> list[CheckResult]:
    results = [
        _bool_required("kis_app_key", settings.kis_app_key),
        _bool_required("kis_app_secret", settings.kis_app_secret),
        _bool_required("kis_account_no", settings.kis_account_no),
        _bool_required("kis_account_product_code", settings.kis_account_product_code),
        CheckResult("kis_env", "OK" if settings.kis_env == "paper" else "FAIL", settings.kis_env),
        CheckResult("real_trading_enabled", "OK" if not settings.real_trading_enabled else "FAIL", str(settings.real_trading_enabled)),
        CheckResult("paper_trading_only", "OK" if settings.paper_trading_only else "FAIL", str(settings.paper_trading_only)),
        CheckResult("order_enabled", "WARN" if settings.order_enabled else "OK", str(settings.order_enabled)),
        CheckResult("auto_trading_enabled", "WARN" if settings.auto_trading_enabled else "OK", str(settings.auto_trading_enabled)),
        CheckResult("trading_max_open_positions", "OK" if settings.trading_max_open_positions > 0 else "WARN", str(settings.trading_max_open_positions)),
        CheckResult(
            "buying_power_check_enabled",
            "OK" if settings.buying_power_check_enabled else "WARN",
            str(settings.buying_power_check_enabled),
        ),
        CheckResult(
            "market_risk_limits",
            "OK",
            (
                f"entries_24h={settings.max_entries_per_market_24h} "
                f"kr_loss_24h={settings.kr_max_realized_loss_24h_krw:,.0f}KRW "
                f"us_loss_24h={settings.us_max_realized_loss_24h_usd:,.2f}USD "
                f"symbol_cooldown={settings.symbol_reentry_cooldown_seconds}s"
            ),
        ),
        CheckResult(
            "telegram",
            "OK" if settings.telegram_enabled and settings.telegram_bot_token and settings.telegram_chat_id else "WARN",
            f"enabled={settings.telegram_enabled} chat_id={_mask(settings.telegram_chat_id)}",
        ),
    ]
    return results


def _check_state_path(path: str) -> CheckResult:
    try:
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return CheckResult("state_path", "FAIL", str(exc))
    return CheckResult("state_path", "OK", str(state_path))


def _check_kis_token(client: KisClient) -> CheckResult:
    try:
        token = client.auth.get_access_token()
    except Exception as exc:
        return CheckResult("kis_token", "FAIL", str(exc))
    return CheckResult("kis_token", "OK", f"expires_at={token.expires_at}")


def _check_domestic_balance(client: KisClient) -> CheckResult:
    try:
        payload = client.get_domestic_balance_raw()
        summary = summarize_domestic_balance(payload)
    except Exception as exc:
        return CheckResult("domestic_balance", "FAIL", str(exc))
    return CheckResult(
        "domestic_balance",
        "OK",
        "cash_krw={cash:,.0f} holdings={holdings}".format(
            cash=summary["cash_krw"],
            holdings=summary["holdings_count"],
        ),
    )


def _check_sessions(settings: Settings) -> CheckResult:
    now = datetime.now(KST)
    policy = SessionPolicy(
        allow_kr_regular=settings.allow_kr_regular_trading,
        allow_us_regular=settings.allow_us_regular_trading,
        allow_us_extended=settings.allow_us_extended_trading,
    )
    kr_open = policy.is_market_open("KR", now=now, session="regular")
    us_open = policy.is_market_open("US", now=now, session=settings.us_order_session)
    active = active_markets(policy, now=now, us_session=settings.us_order_session)
    return CheckResult(
        "sessions",
        "OK" if kr_open or us_open else "WARN",
        "now={now} active_market={active} kr={kr} us={us} kr_reason={kr_reason} us_reason={us_reason}".format(
            now=now.strftime("%Y-%m-%d %H:%M:%S KST"),
            active=",".join(active) if active else "NONE",
            kr=kr_open,
            us=us_open,
            kr_reason="국장 거래 시간" if kr_open else market_closed_reason("KR", now=now),
            us_reason="미장 거래 시간" if us_open else market_closed_reason("US", now=now, session=settings.us_order_session),
        ),
    )


def _check_scanner(settings: Settings, client: KisClient) -> CheckResult:
    us_symbols = _configured_symbols(settings.us_scan_symbols, settings.us_scan_symbols_path)
    kr_symbols = _configured_symbols(settings.kr_scan_symbols, settings.kr_scan_symbols_path)
    if not us_symbols and not kr_symbols:
        return CheckResult("scanner", "FAIL", "No symbols configured.")

    scanner = MomentumScanner(
        quote_client=client,
        rules=_rules_from_settings(settings),
        exchange=settings.us_order_exchange,
        request_delay_seconds=settings.quote_request_delay_seconds,
    )
    try:
        candidates = []
        if us_symbols:
            candidates.extend(
                scanner.scan_us(
                    us_symbols[:2],
                    limit=2,
                    exchange_by_symbol=parse_exchange_map(settings.us_symbol_exchanges),
                )
            )
        if kr_symbols:
            candidates.extend(scanner.scan_kr(kr_symbols[:2], limit=2))
    except Exception as exc:
        return CheckResult("scanner", "FAIL", str(exc))
    return CheckResult("scanner", "OK", f"symbols={len(us_symbols) + len(kr_symbols)} sample_candidates={len(candidates)}")


def _build_client(settings: Settings) -> KisClient:
    return KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        account_product_code=settings.kis_account_product_code,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )


def _configured_symbols(raw_symbols: str | None, path: str | None) -> list[str]:
    symbols = parse_symbol_list(raw_symbols)
    symbols.extend(load_symbols_from_file(path))
    return list(dict.fromkeys(symbols))


def _bool_required(name: str, value: str | None) -> CheckResult:
    return CheckResult(name, "OK" if value else "FAIL", _mask(value))


def _mask(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


if __name__ == "__main__":
    main()
