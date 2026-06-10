import argparse

from app.config import get_settings
from app.disclosures.dart_client import DartClient, evaluate_disclosure_risk


def main() -> None:
    parser = argparse.ArgumentParser(description="Check recent Open DART disclosures for a stock.")
    parser.add_argument("stock_code", help="Korean stock code, for example 005930")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    client = DartClient(settings.dart_api_key)
    disclosures = client.recent_disclosures(args.stock_code, days=args.days, page_count=args.limit)
    risk = evaluate_disclosure_risk(disclosures)

    print(f"stock_code={args.stock_code}")
    print(f"days={args.days}")
    print(f"count={len(disclosures)}")
    print(f"risk_score={risk}")
    for idx, disclosure in enumerate(disclosures[: args.limit], start=1):
        date = disclosure.get("rcept_dt") or "-"
        corp = disclosure.get("corp_name") or "-"
        title = disclosure.get("report_nm") or "-"
        print(f"{idx}. {date} {corp} - {title}")


if __name__ == "__main__":
    main()
