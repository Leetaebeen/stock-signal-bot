import argparse

from app.brokers.kis_client import KisClient, _domestic_output_to_snapshot
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a KIS domestic stock quote.")
    parser.add_argument("symbol", help="Korean stock code, for example 005930")
    parser.add_argument("--name", default=None, help="Optional display name")
    parser.add_argument("--raw", action="store_true", help="Print selected raw KIS output fields.")
    args = parser.parse_args()

    settings = get_settings()
    client = KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    payload = client.get_domestic_price_raw(args.symbol)
    output = payload.get("output") or {}
    snapshot = _domestic_output_to_snapshot(args.symbol, args.name, output)

    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"{snapshot.name} ({snapshot.symbol})")
    print(f"현재가: {snapshot.price:,.0f}원")
    print(f"등락률: {snapshot.change_pct:+.2f}%")
    print(f"누적 거래대금: {snapshot.trading_value_krw / 100_000_000:,.0f}억 원")

    if args.raw:
        keys = [
            "stck_prpr",
            "prdy_vrss",
            "prdy_vrss_sign",
            "prdy_ctrt",
            "stck_oprc",
            "stck_hgpr",
            "stck_lwpr",
            "stck_sdpr",
            "acml_vol",
            "acml_tr_pbmn",
            "hts_kor_isnm",
        ]
        print("raw:")
        for key in keys:
            print(f"  {key}={output.get(key)}")


if __name__ == "__main__":
    main()
