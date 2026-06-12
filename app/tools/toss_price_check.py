import argparse

from app.brokers.toss_client import TossClient
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("--name")
    args = parser.parse_args()

    settings = get_settings()
    client = TossClient(
        api_key=settings.toss_api_key,
        secret_key=settings.toss_secret_key,
        base_url=settings.toss_base_url,
    )
    snapshot = client.get_us_snapshot(args.symbol, name=args.name)
    print(f"{snapshot.name} ({snapshot.symbol})")
    print(f"exchange={snapshot.exchange}")
    print(f"price={snapshot.price:,.2f} USD")
    print(f"change_pct={snapshot.change_pct:+.2f}%")
    print(f"volume_ratio={snapshot.volume_ratio:.2f}x")
    print(f"trading_value_krw={snapshot.trading_value_krw:,.0f}")


if __name__ == "__main__":
    main()
