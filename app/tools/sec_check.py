import argparse

from app.config import get_settings
from app.disclosures.sec_client import SecClient, evaluate_sec_risk


def main() -> None:
    parser = argparse.ArgumentParser(description="Check recent SEC filings for a US ticker.")
    parser.add_argument("ticker", help="US ticker, for example NVDA")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    settings = get_settings()
    client = SecClient(settings.sec_user_agent)
    filings = client.recent_filings(args.ticker, days=args.days, limit=args.limit)
    risk = evaluate_sec_risk(filings)

    print(f"ticker={args.ticker.upper()}")
    print(f"enabled={client.enabled}")
    print(f"status={client.last_status}")
    print(f"days={args.days}")
    print(f"count={len(filings)}")
    print(f"risk_score={risk}")
    if client.enabled and not filings:
        print("note=SEC returned no filings or blocked this request. SEC risk is treated as 0.")
    for idx, filing in enumerate(filings[: args.limit], start=1):
        print(
            f"{idx}. {filing.get('filingDate') or '-'} "
            f"{filing.get('form') or '-'} "
            f"{filing.get('primaryDocDescription') or filing.get('primaryDocument') or '-'}"
        )


if __name__ == "__main__":
    main()
