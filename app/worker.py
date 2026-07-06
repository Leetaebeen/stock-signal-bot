import logging
import time

from app.config import get_settings
from app.trading.runtime import TradingRuntime


logger = logging.getLogger(__name__)


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()
    runtime = TradingRuntime(settings) if settings.auto_trading_enabled else None
    logger.info(
        "worker started kis_env=%s order_enabled=%s real_trading_enabled=%s auto_trading_enabled=%s",
        settings.kis_env,
        settings.order_enabled,
        settings.real_trading_enabled,
        settings.auto_trading_enabled,
    )

    while True:
        if runtime:
            try:
                runtime.run_once()
            except Exception:
                logger.exception("auto trading cycle failed")
        else:
            logger.info(
                "worker idle kis_env=%s order_enabled=%s real_trading_enabled=%s",
                settings.kis_env,
                settings.order_enabled,
                settings.real_trading_enabled,
            )
        time.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    run_forever()
