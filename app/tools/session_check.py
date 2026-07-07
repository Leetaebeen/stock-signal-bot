from datetime import datetime

from app.config import get_settings
from app.trading.sessions import KST, SessionPolicy, is_kr_regular_open, is_us_extended_open, is_us_regular_open


def main() -> None:
    settings = get_settings()
    now = datetime.now(KST)
    policy = SessionPolicy(
        allow_kr_regular=settings.allow_kr_regular_trading,
        allow_us_regular=settings.allow_us_regular_trading,
        allow_us_extended=settings.allow_us_extended_trading,
    )

    print("session_check")
    print(f"now_kst={now.strftime('%Y-%m-%d %H:%M:%S KST')}")
    print(f"kr_regular_open={is_kr_regular_open(now)}")
    print(f"us_regular_open={is_us_regular_open(now)}")
    print(f"us_pre_open={is_us_extended_open(now, 'pre')}")
    print(f"us_after_open={is_us_extended_open(now, 'after')}")
    print(f"allow_kr_regular={settings.allow_kr_regular_trading}")
    print(f"allow_us_regular={settings.allow_us_regular_trading}")
    print(f"allow_us_extended={settings.allow_us_extended_trading}")
    print(f"policy_kr_can_trade={policy.is_market_open('KR', now, 'regular')}")
    print(f"policy_us_can_trade={policy.is_market_open('US', now, settings.us_order_session)}")


if __name__ == "__main__":
    main()
