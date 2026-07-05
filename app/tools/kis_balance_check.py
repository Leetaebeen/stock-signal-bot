from app.brokers.kis_client import KisClient, summarize_domestic_balance
from app.config import get_settings


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
    client.assert_readonly_paper_mode(
        paper_trading_only=settings.paper_trading_only,
        real_trading_enabled=settings.real_trading_enabled,
    )
    summary = summarize_domestic_balance(client.get_domestic_balance_raw())

    print("KIS paper domestic balance check.")
    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"account={_mask_account(settings.kis_account_no, settings.kis_account_product_code)}")
    print(f"holdings_count={summary['holdings_count']}")
    print(f"cash_krw={summary['cash_krw']:,.0f}")
    print(f"total_eval_krw={summary['total_eval_krw']:,.0f}")
    print(f"purchase_amount_krw={summary['purchase_amount_krw']:,.0f}")
    print(f"profit_loss_krw={summary['profit_loss_krw']:,.0f}")
    print(f"profit_loss_pct={summary['profit_loss_pct']:+.2f}%")
    print(f"order_enabled={settings.order_enabled}")
    print(f"real_trading_enabled={settings.real_trading_enabled}")


def _mask_account(account_no: str | None, product_code: str | None) -> str:
    if not account_no or not product_code:
        return "missing"
    return f"{account_no[:2]}****{account_no[-2:]}-{product_code}"


if __name__ == "__main__":
    main()
