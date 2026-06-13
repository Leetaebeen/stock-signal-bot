import asyncio
import logging

from app.alerts.message_builder import build_scan_start_message, build_signal_message
from app.alerts.telegram import TelegramAlerter
from app.brokers.toss_client import TossClient
from app.brokers.toss_rank_client import TossRankClient
from app.config import Settings, get_settings, parse_enabled_markets
from app.db import (
    init_db,
    save_scan_rejection_report,
    save_signal,
    was_recently_alerted,
)
from app.disclosures.sec_client import SecClient
from app.logging_config import setup_logging
from app.market_clock import is_us_market_open
from app.scanners.us_scanner import scan_us_market
from app.signals.filters import filter_candidates, filter_config_from_settings
from app.signals.rejection_report import build_rejection_report
from app.signals.scorer import score_snapshot
from app.signals.selector import select_strongest

logger = logging.getLogger(__name__)


def build_market_client(settings: Settings) -> TossRankClient:
    if settings.market_mode != "toss_rank":
        raise RuntimeError("Only MARKET_MODE=toss_rank is supported.")

    toss_client = TossClient(
        api_key=settings.toss_api_key,
        secret_key=settings.toss_secret_key,
        base_url=settings.toss_base_url,
        token_cache_path=settings.toss_token_cache_path,
    )
    return TossRankClient(
        toss_client=toss_client,
        request_interval_seconds=settings.toss_request_interval_seconds,
        rank_count=settings.toss_rank_count,
        us_symbols_path=settings.us_symbols_path,
        scan_cursor_path=settings.toss_scan_cursor_path,
        spike_cache_path=settings.toss_spike_cache_path,
        price_sweep_count=settings.toss_price_sweep_count,
        spike_1m_pct=settings.toss_spike_1m_pct,
        spike_5m_pct=settings.toss_spike_5m_pct,
        spike_20m_pct=settings.toss_spike_20m_pct,
        spike_max_candidates=settings.toss_spike_max_candidates,
        sec_client=SecClient(settings.sec_user_agent),
    )


async def run_once(settings: Settings, send_alert: bool = True, markets: set[str] | None = None):
    init_db(settings.sqlite_path)
    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    selected_markets = (markets or enabled_markets) & enabled_markets
    if "US" not in selected_markets:
        logger.info("US market is not selected. selected_markets=%s", ",".join(sorted(selected_markets)))
        return None

    client = build_market_client(settings)
    snapshots = await scan_us_market(client)

    filter_config = filter_config_from_settings(settings)
    rejection_report = build_rejection_report(snapshots, filter_config=filter_config)
    save_scan_rejection_report(settings.sqlite_path, ",".join(sorted(selected_markets)), rejection_report)

    filtered_snapshots = filter_candidates(snapshots, filter_config)
    candidates = [score_snapshot(snapshot) for snapshot in filtered_snapshots]
    logger.info(
        "scan markets=%s candidates=%s filtered=%s scored=%s",
        ",".join(sorted(selected_markets)),
        len(snapshots),
        len(filtered_snapshots),
        len(candidates),
    )

    strongest = select_strongest(candidates, min_score=settings.min_alert_score)
    if strongest is None:
        logger.info("scan selected=None min_score=%s", settings.min_alert_score)
        return None

    snap = strongest.snapshot
    logger.info(
        "scan selected=%s:%s score=%s price=%s change_pct=%s volume_ratio=%s",
        snap.market,
        snap.symbol,
        strongest.score,
        snap.price,
        snap.change_pct,
        snap.volume_ratio,
    )

    recently_alerted = was_recently_alerted(settings.sqlite_path, snap.symbol, settings.alert_cooldown_minutes)
    alert_sent = False
    if send_alert and not recently_alerted:
        alerter = TelegramAlerter(
            settings.telegram_enabled,
            settings.telegram_bot_token,
            settings.telegram_chat_id,
        )
        alert_sent = await alerter.send(build_signal_message(strongest))
        logger.info(
            "signal alert %s %s:%s",
            "sent" if alert_sent else "skipped",
            snap.market,
            snap.symbol,
        )
    else:
        logger.info("signal alert suppressed by cooldown or disabled %s:%s", snap.market, snap.symbol)

    save_signal(settings.sqlite_path, strongest, alerted=alert_sent)
    return strongest


async def main_loop() -> None:
    setup_logging()
    settings = get_settings()
    init_db(settings.sqlite_path)

    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    alerter = TelegramAlerter(
        settings.telegram_enabled,
        settings.telegram_bot_token,
        settings.telegram_chat_id,
    )
    await alerter.send(build_scan_start_message(",".join(sorted(enabled_markets))))

    while True:
        if "US" not in enabled_markets or not is_us_market_open():
            logger.info("all markets closed. waiting %ss", settings.scan_interval_seconds)
            await asyncio.sleep(settings.scan_interval_seconds)
            continue

        try:
            strongest = await run_once(settings, send_alert=True, markets={"US"})
            if strongest:
                logger.info("loop selected US:%s score=%s", strongest.snapshot.symbol, strongest.score)
            else:
                logger.info("loop no strong signal")
        except Exception:
            logger.exception("worker loop failed; retrying next cycle")

        await asyncio.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main_loop())
