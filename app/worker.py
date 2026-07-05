import logging
import time
from datetime import datetime, timedelta, timezone

from app.alerts.telegram import TelegramAlerter
from app.config import get_settings


KST = timezone(timedelta(hours=9))
logger = logging.getLogger(__name__)


def build_start_message() -> str:
    settings = get_settings()
    return (
        "[KIS 모의투자 봇 시작]\n"
        "------------------------------\n"
        "국장/미장 모의투자 학습 시스템을 준비 중입니다.\n"
        f"KIS 환경: {settings.kis_env}\n"
        f"주문 활성화: {settings.order_enabled}\n"
        f"실거래 활성화: {settings.real_trading_enabled}\n"
        f"시간: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S KST')}"
    )


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    settings = get_settings()
    alerter = TelegramAlerter(
        enabled=settings.telegram_enabled,
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )
    sent = alerter.send(build_start_message())
    logger.info("worker started telegram_sent=%s", sent)

    while True:
        logger.info(
            "worker idle kis_env=%s order_enabled=%s real_trading_enabled=%s",
            settings.kis_env,
            settings.order_enabled,
            settings.real_trading_enabled,
        )
        time.sleep(60)


if __name__ == "__main__":
    run_forever()
