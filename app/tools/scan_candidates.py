from app.brokers.kis_client import KisClient
from app.config import get_settings
from app.scanners.momentum import MomentumScanner, parse_symbol_list


def main() -> None:
    settings = get_settings()
    client = KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        account_product_code=settings.kis_account_product_code,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    scanner = MomentumScanner(
        quote_client=client,
        exchange=settings.us_order_exchange,
        request_delay_seconds=settings.quote_request_delay_seconds,
    )
    candidates = scanner.scan_us(parse_symbol_list(settings.us_scan_symbols), limit=settings.scan_candidate_limit)

    print("scan_candidates")
    print(f"symbols={len(parse_symbol_list(settings.us_scan_symbols))}")
    print(f"candidates={len(candidates)}")
    for candidate in candidates:
        signal = candidate.signal
        print(
            f"{signal.symbol} {signal.name} "
            f"price={signal.price:,.2f} change={signal.change_pct:+.2f}% "
            f"volume_ratio={signal.volume_ratio:.2f} value_krw={signal.trading_value_krw:,.0f} "
            f"score={candidate.score:.2f}"
        )


if __name__ == "__main__":
    main()
