import argparse

from app.brokers.kis_client import KisClient
from app.brokers.kis_rank_client import _extract_rows, _first_text
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Check KIS overseas ranking candidates.")
    parser.add_argument("--exchange", default="NAS", choices=["NAS", "NYS", "AMS"])
    parser.add_argument("--source", default="volume_surge", choices=["volume_surge", "volume_power"])
    parser.add_argument("--show", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    client = KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )
    if args.source == "volume_surge":
        payload = client.get_overseas_volume_surge_raw(exchange=args.exchange)
    else:
        payload = client.get_overseas_volume_power_raw(exchange=args.exchange)
    rows = _extract_rows(payload)

    print(f"env={settings.kis_env}")
    print(f"base_url={client.base_url}")
    print(f"exchange={args.exchange}")
    print(f"source={args.source}")
    print(f"rows={len(rows)}")
    for idx, row in enumerate(rows[: args.show], start=1):
        symbol = _first_text(row, ["symb", "SYMB", "rsym", "ovrs_pdno", "pdno", "symbol"])
        name = _first_text(row, ["name", "ename", "ovrs_item_name", "prdt_name"])
        price = _first_text(row, ["last", "ovrs_nmix_prpr", "price"])
        rate = _first_text(row, ["rate", "prdy_ctrt", "diff_rate"])
        volume = _first_text(row, ["tvol", "acml_vol", "volume"])
        print(f"{idx}. {name or '-'} ({symbol or '-'}) price={price or '-'} rate={rate or '-'} volume={volume or '-'}")


if __name__ == "__main__":
    main()
