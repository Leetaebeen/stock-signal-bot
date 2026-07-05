from datetime import datetime, timedelta, timezone

from app.alerts.telegram import TelegramAlerter
from app.config import get_settings


KST = timezone(timedelta(hours=9))


def main() -> None:
    settings = get_settings()
    alerter = TelegramAlerter(
        enabled=settings.telegram_enabled,
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )
    message = (
        "[KIS 모의투자 봇 알림 테스트]\n"
        "------------------------------\n"
        "국장/미장 모의투자 준비 상태를 확인했습니다.\n"
        f"KIS 환경: {settings.kis_env}\n"
        f"주문 활성화: {settings.order_enabled}\n"
        f"실거래 활성화: {settings.real_trading_enabled}\n"
        f"시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}"
    )
    sent = alerter.send(message)
    print(f"telegram_enabled={settings.telegram_enabled}")
    print(f"sent={sent}")


if __name__ == "__main__":
    main()
