import asyncio
import json
import logging
from dataclasses import replace

from app.alerts.message_builder import (
    build_scan_start_message,
    build_signal_message,
    build_state_stop_message,
    build_state_target_reached_message,
    build_state_uptrend_message,
)
from app.ai.analyst import ai_allows_alert, analyze_candidate
from app.alerts.telegram import TelegramAlerter
from app.brokers.kis_client import KisClient
from app.brokers.kis_rank_client import KisRankClient
from app.brokers.toss_client import TossClient
from app.brokers.toss_rank_client import TossRankClient
from app.config import Settings, get_settings, parse_enabled_markets
from app.db import (
    count_ai_analysis_today,
    create_signal_state,
    create_signal_outcomes,
    get_due_signal_outcomes,
    get_active_signal_state,
    get_active_signal_states,
    get_recent_ai_analysis,
    init_db,
    parse_outcome_horizons,
    save_ai_analysis,
    save_scan_rejection_report,
    save_signal,
    update_signal_outcome,
    update_signal_state,
    was_recently_alerted,
)
from app.disclosures.dart_client import DartClient
from app.disclosures.sec_client import SecClient
from app.logging_config import setup_logging
from app.market_clock import is_kr_regular_market_open, is_us_market_open
from app.models import MarketSnapshot
from app.scanners.kr_scanner import scan_kr_market
from app.scanners.us_scanner import scan_us_market
from app.signals.filters import filter_candidates, filter_config_from_settings, is_excluded_us_product
from app.signals.rejection_report import build_rejection_report
from app.signals.scorer import score_snapshot
from app.signals.selector import select_strongest
from app.signals.state_machine import evaluate_signal_status
from app.signals.trade_plan import build_trade_plan

logger = logging.getLogger(__name__)


def build_kis_client(settings: Settings) -> KisClient:
    return KisClient(
        app_key=settings.kis_app_key,
        app_secret=settings.kis_app_secret,
        account_no=settings.kis_account_no,
        env=settings.kis_env,
        token_cache_path=settings.kis_token_cache_path,
    )


def build_market_client(settings: Settings):
    if settings.market_mode == "kis_rank":
        kis_client = build_kis_client(settings)
        return KisRankClient(
            kis_client=kis_client,
            request_interval_seconds=settings.kis_request_interval_seconds,
            rank_count=settings.kis_rank_count,
            dart_client=DartClient(settings.dart_api_key),
            sec_client=SecClient(settings.sec_user_agent),
        )
    if settings.market_mode == "toss_rank":
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
    raise RuntimeError("Only MARKET_MODE=kis_rank or MARKET_MODE=toss_rank is supported.")


async def run_once(settings: Settings, send_alert: bool = True, markets: set[str] | None = None):
    init_db(settings.sqlite_path)
    client = build_market_client(settings)
    snapshots = []
    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    markets = (markets or enabled_markets) & enabled_markets
    if "KR" in markets:
        snapshots.extend(await scan_kr_market(client))
    if "US" in markets:
        snapshots.extend(await scan_us_market(client))

    filter_config = filter_config_from_settings(settings)
    rejection_report = build_rejection_report(snapshots, filter_config=filter_config)
    save_scan_rejection_report(settings.sqlite_path, ",".join(sorted(markets)), rejection_report)

    filtered_snapshots = filter_candidates(snapshots, filter_config)
    candidates = [score_snapshot(snapshot) for snapshot in filtered_snapshots]
    logger.info(
        "scan markets=%s candidates=%s filtered=%s scored=%s",
        ",".join(sorted(markets)),
        len(snapshots),
        len(filtered_snapshots),
        len(candidates),
    )

    strongest = select_strongest(candidates, min_score=settings.min_alert_score)
    if strongest is None:
        logger.info("scan selected=None min_score=%s", settings.min_alert_score)
        return None

    logger.info(
        "scan selected=%s:%s score=%s price=%s change_pct=%s",
        strongest.snapshot.market,
        strongest.snapshot.symbol,
        strongest.score,
        strongest.snapshot.price,
        strongest.snapshot.change_pct,
    )

    if settings.ai_analysis_enabled:
        if strongest.score < settings.ai_min_rule_score:
            logger.info(
                "ai skipped by rule score %s:%s score=%s min=%s",
                strongest.snapshot.market,
                strongest.snapshot.symbol,
                strongest.score,
                settings.ai_min_rule_score,
            )
            save_signal(settings.sqlite_path, strongest, alerted=False)
            return None

        cached_analysis = get_recent_ai_analysis(
            settings.sqlite_path,
            strongest.snapshot.market,
            strongest.snapshot.symbol,
            settings.ai_cache_ttl_minutes,
        )
        if cached_analysis:
            strongest = replace(strongest, ai_analysis=cached_analysis)
            logger.info(
                "ai cache hit %s:%s recommendation=%s confidence=%s",
                strongest.snapshot.market,
                strongest.snapshot.symbol,
                cached_analysis.recommendation,
                cached_analysis.confidence,
            )
        elif count_ai_analysis_today(settings.sqlite_path) >= settings.ai_daily_limit:
            logger.warning("ai daily limit reached limit=%s", settings.ai_daily_limit)
            save_signal(settings.sqlite_path, strongest, alerted=False)
            return None
        else:
            try:
                strongest = await analyze_candidate(strongest, settings)
            except Exception:
                logger.exception("ai analysis failed %s:%s", strongest.snapshot.market, strongest.snapshot.symbol)
                save_signal(settings.sqlite_path, strongest, alerted=False)
                if settings.ai_analysis_required:
                    return None
            else:
                save_ai_analysis(settings.sqlite_path, strongest)

        if strongest.ai_analysis:
            logger.info(
                "ai analysis %s:%s recommendation=%s confidence=%s",
                strongest.snapshot.market,
                strongest.snapshot.symbol,
                strongest.ai_analysis.recommendation,
                strongest.ai_analysis.confidence,
            )
        if not ai_allows_alert(strongest, settings.ai_min_confidence):
            save_signal(settings.sqlite_path, strongest, alerted=False)
            return None

    active_state = get_active_signal_state(
        settings.sqlite_path,
        strongest.snapshot.market,
        strongest.snapshot.symbol,
    )
    if active_state:
        logger.info("signal already active %s:%s", strongest.snapshot.market, strongest.snapshot.symbol)
        save_signal(settings.sqlite_path, strongest, alerted=False)
        return strongest

    recently_alerted = was_recently_alerted(
        settings.sqlite_path,
        strongest.snapshot.symbol,
        settings.alert_cooldown_minutes,
    )
    should_try_alert = send_alert and not recently_alerted
    alert_sent = False
    if should_try_alert:
        alerter = TelegramAlerter(
            settings.telegram_enabled,
            settings.telegram_bot_token,
            settings.telegram_chat_id,
        )
        alert_sent = await alerter.send(build_signal_message(strongest))
        if alert_sent:
            logger.info("signal alert sent %s:%s", strongest.snapshot.market, strongest.snapshot.symbol)
            state_id = create_signal_state(settings.sqlite_path, strongest, build_trade_plan(strongest))
            create_signal_outcomes(
                settings.sqlite_path,
                state_id,
                strongest,
                parse_outcome_horizons(settings.outcome_horizon_minutes),
            )
        else:
            logger.info("signal alert skipped or disabled %s:%s", strongest.snapshot.market, strongest.snapshot.symbol)
    save_signal(settings.sqlite_path, strongest, alerted=alert_sent)
    return strongest


async def monitor_active_signals(settings: Settings) -> None:
    states = get_active_signal_states(settings.sqlite_path)
    if not states:
        return

    client = build_market_client(settings)
    alerter = TelegramAlerter(
        settings.telegram_enabled,
        settings.telegram_bot_token,
        settings.telegram_chat_id,
    )

    for state in states:
        if _active_state_is_excluded_us_product(state):
            update_signal_state(
                settings.sqlite_path,
                int(state["id"]),
                "CLEARED",
                float(state["current_price"]),
                float(state["last_alert_price"]),
            )
            logger.info("cleared excluded active signal %s:%s", state["market"], state["symbol"])
            continue

        try:
            if state["market"] == "KR":
                if not isinstance(client, KisRankClient):
                    raise RuntimeError("KR active signal monitoring requires MARKET_MODE=kis_rank.")
                snapshot = client.kis_client.get_domestic_price(state["symbol"], name=state["name"])
            else:
                snapshot = _get_us_snapshot_from_market_client(client, state["symbol"], state["name"], _extract_snapshot_exchange(state))
        except Exception:
            logger.exception("active quote failed %s", state["symbol"])
            await asyncio.sleep(_market_request_interval(settings))
            continue

        status = evaluate_signal_status(
            current_price=snapshot.price,
            target_price=float(state["target_price"]),
            stop_price=float(state["stop_price"]),
            last_alert_price=float(state["last_alert_price"]),
        )

        if status == "WATCHING":
            update_signal_state(
                settings.sqlite_path,
                state["id"],
                "WATCHING",
                snapshot.price,
                float(state["last_alert_price"]),
            )
        elif status == "UPTREND":
            await alerter.send(build_state_uptrend_message(state, snapshot.price, snapshot.change_pct))
            update_signal_state(settings.sqlite_path, state["id"], "UPTREND", snapshot.price, snapshot.price)
            logger.info("uptrend alert sent %s", state["symbol"])
        elif status == "TARGET_REACHED":
            await alerter.send(build_state_target_reached_message(state, snapshot.price, snapshot.change_pct))
            update_signal_state(settings.sqlite_path, state["id"], "TARGET_REACHED", snapshot.price, snapshot.price)
            logger.info("target alert sent %s", state["symbol"])
        elif status == "STOPPED":
            await alerter.send(build_state_stop_message(state, snapshot.price, snapshot.change_pct))
            update_signal_state(settings.sqlite_path, state["id"], "STOPPED", snapshot.price, snapshot.price)
            logger.info("stop alert sent %s", state["symbol"])

        await asyncio.sleep(_market_request_interval(settings))


async def monitor_signal_outcomes(settings: Settings) -> None:
    outcomes = get_due_signal_outcomes(settings.sqlite_path, limit=20)
    if not outcomes:
        return

    client = build_market_client(settings)
    for outcome in outcomes:
        try:
            snapshot = _get_outcome_snapshot(client, outcome)
        except Exception:
            logger.exception("outcome quote failed %s:%s", outcome["market"], outcome["symbol"])
            await asyncio.sleep(_market_request_interval(settings))
            continue

        update_signal_outcome(settings.sqlite_path, int(outcome["id"]), snapshot.price)
        logger.info(
            "outcome checked %s:%s horizon=%sm price=%s",
            outcome["market"],
            outcome["symbol"],
            outcome["horizon_minutes"],
            snapshot.price,
        )
        await asyncio.sleep(_market_request_interval(settings))


def _get_outcome_snapshot(client, outcome: dict):
    if outcome["market"] == "KR":
        if not isinstance(client, KisRankClient):
            raise RuntimeError("KR outcome monitoring requires MARKET_MODE=kis_rank.")
        return client.kis_client.get_domestic_price(outcome["symbol"], name=outcome["name"])

    return _get_us_snapshot_from_market_client(client, outcome["symbol"], outcome["name"], _extract_snapshot_exchange(outcome))


def _get_us_snapshot_from_market_client(client, symbol: str, name: str, exchange: str | None = None):
    if isinstance(client, TossRankClient):
        return client.get_us_snapshot(symbol, name=name, exchange=exchange)
    if isinstance(client, KisRankClient):
        return _get_us_snapshot(client.kis_client, symbol, name, exchange=exchange)
    raise RuntimeError(f"Unsupported market client for US quote: {type(client).__name__}")


def _market_request_interval(settings: Settings) -> float:
    if settings.market_mode == "toss_rank":
        return settings.toss_request_interval_seconds
    return settings.kis_request_interval_seconds


def _get_us_snapshot(kis_client: KisClient, symbol: str, name: str, exchange: str | None = None):
    last_error: Exception | None = None
    exchanges = [exchange] if exchange else ["NAS", "NYS", "AMS"]
    for current_exchange in exchanges:
        if not current_exchange:
            continue
        try:
            snapshot = kis_client.get_overseas_price(symbol, exchange=current_exchange, name=name)
            if snapshot.price <= 0:
                raise RuntimeError(f"US quote returned zero price {current_exchange}:{symbol}")
            return snapshot
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise RuntimeError(f"US quote failed for {symbol}")


def _extract_snapshot_exchange(row: dict) -> str | None:
    raw_json = row.get("raw_json")
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except (TypeError, ValueError):
        return None
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        return None
    exchange = snapshot.get("exchange")
    return str(exchange).strip().upper() if exchange else None


def _active_state_is_excluded_us_product(state: dict) -> bool:
    if state.get("market") != "US":
        return False
    return is_excluded_us_product(
        MarketSnapshot(
            symbol=str(state.get("symbol") or ""),
            name=str(state.get("name") or ""),
            market="US",
            price=float(state.get("current_price") or 0),
            change_pct=0,
            volume_ratio=0,
            trading_value_krw=0,
        )
    )


async def main_loop() -> None:
    setup_logging()
    settings = get_settings()
    init_db(settings.sqlite_path)
    startup_alerter = TelegramAlerter(
        settings.telegram_enabled,
        settings.telegram_bot_token,
        settings.telegram_chat_id,
    )
    enabled_markets = parse_enabled_markets(settings.enabled_markets)
    await startup_alerter.send(build_scan_start_message(",".join(sorted(enabled_markets))))
    while True:
        open_markets: set[str] = set()
        if "KR" in enabled_markets and is_kr_regular_market_open():
            open_markets.add("KR")
        if "US" in enabled_markets and is_us_market_open():
            open_markets.add("US")

        if not open_markets:
            logger.info("all markets closed. waiting %ss", settings.scan_interval_seconds)
            await asyncio.sleep(settings.scan_interval_seconds)
            continue

        try:
            await monitor_active_signals(settings)
            await monitor_signal_outcomes(settings)
            strongest = await run_once(settings, send_alert=True, markets=open_markets)
            if strongest:
                snap = strongest.snapshot
                logger.info("loop selected %s:%s score=%s", snap.market, snap.symbol, strongest.score)
            else:
                logger.info("loop no strong signal")
        except Exception:
            logger.exception("worker loop failed; retrying next cycle")

        await asyncio.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main_loop())
