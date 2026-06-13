import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.brokers.rate_limiter import RateLimiter
from app.brokers.toss_client import TossClient, build_us_snapshot_from_toss
from app.disclosures.sec_client import SecClient
from app.models import MarketSnapshot
from app.universe.us_symbols import load_us_symbols


US_STOCK_MARKETS = {"NASDAQ", "NYSE", "AMEX"}
US_STOCK_TYPES = {"STOCK", "FOREIGN_STOCK", "DEPOSITARY_RECEIPT"}


class TossRankClient:
    def __init__(
        self,
        toss_client: TossClient,
        request_interval_seconds: float,
        rank_count: int,
        us_symbols_path: str | None = None,
        scan_cursor_path: str | None = None,
        spike_cache_path: str | None = None,
        price_sweep_count: int = 0,
        spike_1m_pct: float = 3.0,
        spike_5m_pct: float = 8.0,
        spike_20m_pct: float = 15.0,
        spike_max_candidates: int = 20,
        sec_client: SecClient | None = None,
    ) -> None:
        self.toss_client = toss_client
        self.rate_limiter = RateLimiter(request_interval_seconds)
        self.rank_count = rank_count
        self.us_symbols_path = us_symbols_path
        self.scan_cursor_path = Path(scan_cursor_path or "data/toss_scan_cursor.txt")
        self.spike_cache_path = Path(spike_cache_path or "data/toss_price_cache.json")
        self.price_sweep_count = price_sweep_count
        self.spike_thresholds = {
            "1m": spike_1m_pct,
            "5m": spike_5m_pct,
            "20m": spike_20m_pct,
        }
        self.spike_max_candidates = spike_max_candidates
        self.sec_client = sec_client

    async def get_us_snapshots(self) -> list[MarketSnapshot]:
        all_symbols = load_us_symbols(self.us_symbols_path)
        prices = self._sweep_prices(all_symbols)
        spike_symbols = self._detect_spike_symbols(prices)
        if spike_symbols:
            symbols = spike_symbols
        else:
            symbols = self._next_symbol_batch(all_symbols)
            prices = {symbol: prices[symbol] for symbol in symbols if symbol in prices} or self.toss_client.get_prices(symbols)

        self.rate_limiter.wait()
        stocks = self.toss_client.get_stocks(symbols)
        us_symbols = [
            symbol
            for symbol in symbols
            if _is_supported_us_stock(stocks.get(symbol, {}))
        ]
        if not us_symbols:
            return []

        usd_krw = self.toss_client.get_usd_krw_rate()
        snapshots: list[MarketSnapshot] = []

        for symbol in us_symbols:
            price_row = prices.get(symbol)
            if not price_row:
                continue
            self.rate_limiter.wait()
            try:
                candles = self.toss_client.get_candles(symbol, interval="1d", count=8)
                self.rate_limiter.wait()
                minute_candles = self.toss_client.get_candles(symbol, interval="1m", count=200)
                snapshot = build_us_snapshot_from_toss(
                    symbol=symbol,
                    price_row=price_row,
                    stock_row=stocks.get(symbol, {}),
                    candles=candles,
                    usd_krw=usd_krw,
                    minute_candles=minute_candles,
                )
                snapshots.append(replace(snapshot, disclosure_risk=self._sec_risk_score(symbol)))
            except Exception as exc:
                print(f"Toss US quote failed {symbol}: {exc}")

        return sorted(snapshots, key=lambda snapshot: _sort_score(snapshot), reverse=True)

    def get_us_snapshot(self, symbol: str, name: str | None = None, exchange: str | None = None) -> MarketSnapshot:
        self.rate_limiter.wait()
        return self.toss_client.get_us_snapshot(symbol, name=name, exchange=exchange)

    def _sec_risk_score(self, symbol: str) -> float:
        if not self.sec_client:
            return 0.0
        try:
            return self.sec_client.risk_score(symbol)
        except Exception as exc:
            print(f"SEC risk check failed {symbol}: {exc}")
            return 0.0

    def _next_symbol_batch(self, symbols: list[str]) -> list[str]:
        if not symbols:
            return []
        batch_size = max(1, min(self.rank_count, len(symbols)))
        cursor = self._load_cursor() % len(symbols)
        end = cursor + batch_size
        if end <= len(symbols):
            batch = symbols[cursor:end]
        else:
            batch = symbols[cursor:] + symbols[: end - len(symbols)]
        self._save_cursor(end % len(symbols))
        return batch

    def _load_cursor(self) -> int:
        try:
            return int(self.scan_cursor_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            return 0

    def _save_cursor(self, cursor: int) -> None:
        self.scan_cursor_path.parent.mkdir(parents=True, exist_ok=True)
        self.scan_cursor_path.write_text(str(cursor), encoding="utf-8")

    def _sweep_prices(self, symbols: list[str]) -> dict[str, dict]:
        sweep_symbols = symbols
        if self.price_sweep_count > 0:
            sweep_symbols = symbols[: self.price_sweep_count]
        if not sweep_symbols:
            return {}

        prices: dict[str, dict] = {}
        for batch in _chunks(sweep_symbols, 200):
            self.rate_limiter.wait()
            prices.update(self.toss_client.get_prices(batch))
        return prices

    def _detect_spike_symbols(self, prices: dict[str, dict]) -> list[str]:
        now = datetime.now(timezone.utc)
        cache = _load_price_cache(self.spike_cache_path)
        spikes = _detect_price_spikes(prices, cache, now, self.spike_thresholds)
        _update_price_cache(self.spike_cache_path, cache, prices, now)
        return [
            item["symbol"]
            for item in sorted(spikes, key=lambda row: row["score"], reverse=True)[: self.spike_max_candidates]
        ]


def _is_supported_us_stock(stock: dict) -> bool:
    market = str(stock.get("market") or "").upper()
    security_type = str(stock.get("securityType") or "").upper()
    status = str(stock.get("status") or "").upper()
    is_common_share = stock.get("isCommonShare")

    if market not in US_STOCK_MARKETS:
        return False
    if security_type and security_type not in US_STOCK_TYPES:
        return False
    if status and status != "ACTIVE":
        return False
    if is_common_share is False:
        return False
    return True


def _sort_score(snapshot: MarketSnapshot) -> float:
    return (snapshot.volume_ratio * 10) + snapshot.change_pct + (snapshot.trading_value_krw / 10_000_000_000)


def _load_price_cache(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(symbol).upper(): rows
        for symbol, rows in payload.items()
        if isinstance(rows, list)
    }


def _update_price_cache(path: Path, cache: dict[str, list[dict]], prices: dict[str, dict], now: datetime) -> None:
    cutoff = (now - timedelta(minutes=30)).timestamp()
    timestamp = now.timestamp()
    for symbol, row in prices.items():
        price = _price_from_row(row)
        if price <= 0:
            continue
        history = [
            item
            for item in cache.get(symbol, [])
            if isinstance(item, dict) and float(item.get("ts") or 0) >= cutoff
        ]
        history.append({"ts": timestamp, "price": price})
        cache[symbol] = history[-60:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _detect_price_spikes(
    prices: dict[str, dict],
    cache: dict[str, list[dict]],
    now: datetime,
    thresholds: dict[str, float],
) -> list[dict]:
    windows = {"1m": 60, "5m": 5 * 60, "20m": 20 * 60}
    spikes: list[dict] = []
    now_ts = now.timestamp()
    for symbol, row in prices.items():
        current = _price_from_row(row)
        if current <= 0:
            continue
        history = cache.get(symbol, [])
        best_score = 0.0
        best_window = None
        for label, seconds in windows.items():
            previous = _price_at_or_before(history, now_ts - seconds)
            if previous <= 0:
                continue
            move_pct = ((current - previous) / previous) * 100
            threshold = thresholds[label]
            if move_pct >= threshold and move_pct > best_score:
                best_score = move_pct
                best_window = label
        if best_window:
            spikes.append({"symbol": symbol, "score": best_score, "window": best_window})
    return spikes


def _price_at_or_before(history: list[dict], target_ts: float) -> float:
    candidates = [
        item
        for item in history
        if isinstance(item, dict) and float(item.get("ts") or 0) <= target_ts
    ]
    if not candidates:
        return 0.0
    latest = max(candidates, key=lambda item: float(item.get("ts") or 0))
    return float(latest.get("price") or 0)


def _price_from_row(row: dict) -> float:
    try:
        return float(str(row.get("lastPrice") or "0").replace(",", ""))
    except ValueError:
        return 0.0


def _chunks(items: list[str], size: int):
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]
