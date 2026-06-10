import argparse

from app.brokers.kis_client import KisClient
from app.brokers.kis_rank_client import _extract_rows, _first_text
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check KIS domestic fluctuation ranking.")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--show", type=int, default=10)
    parser.add_argument(
        "--source",
        choices=["fluctuation", "volume_increase", "trading_value"],
        default="fluctuation",
    )
    args = parser.parse_args()

    settings = get_settings()
    client = KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    if args.source == "fluctuation":
        payload = client.get_domestic_fluctuation_rank_raw(count=args.count)
    elif args.source == "volume_increase":
        payload = client.get_domestic_volume_rank_raw(rank_type="1")
    else:
        payload = client.get_domestic_volume_rank_raw(rank_type="3")
    rows = _extract_rows(payload)

    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"source={args.source}")
    print(f"rows={len(rows)}")
    for idx, row in enumerate(rows[: args.show], start=1):
        symbol = _first_text(row, ["stck_shrn_iscd", "mksc_shrn_iscd", "iscd", "pdno"])
        name = _first_text(row, ["hts_kor_isnm", "data_rank_name", "prdt_name", "name"])
        rate = _first_text(row, ["prdy_ctrt", "data_rank", "stck_prdy_ctrt", "flu_rt"])
        price = _first_text(row, ["stck_prpr", "now_prc", "last"])
        volume = _first_text(row, ["acml_vol", "vol", "tvol"])
        print(f"{idx}. {name or '-'} ({symbol or '-'}) price={price or '-'} rate={rate or '-'} volume={volume or '-'}")


if __name__ == "__main__":
    main()
