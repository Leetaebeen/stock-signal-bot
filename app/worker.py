import logging
import time

from app.config import get_settings


logger = logging.getLogger(__name__)


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    logger.info(
        "worker started kis_env=%s order_enabled=%s real_trading_enabled=%s",
        settings.kis_env,
        settings.order_enabled,
        settings.real_trading_enabled,
    )

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
