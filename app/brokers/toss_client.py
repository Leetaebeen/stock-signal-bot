from typing import Any, Iterable

import httpx

from app.brokers.toss_auth import TOSS_DEFAULT_BASE_URL, TossAuthClient
from app.models import MarketSnapshot


USD_KRW_FALLBACK = 1350.0


class TossClient:
    def __init__(
        self,
        api_key: str | None,
        secret_key: str | None,
        base_url: str | None = None,
        token_cache_path: str = "data/toss_token.json",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.http_client = http_client or httpx.Client(timeout=10)
        self.base_url = (base_url or TOSS_DEFAULT_BASE_URL).rstrip("/")
        self.auth_client = TossAuthClient(
            api_key=api_key,
            secret_key=secret_key,
            base_url=self.base_url,
            token_cache_path=token_cache_path,
            http_client=self.http_client,
        )

    def get_prices(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        clean_symbols = _clean_symbols(symbols)
        if not clean_symbols:
            return {}

        prices: dict[str, dict[str, Any]] = {}
        for batch in _chunks(clean_symbols, 200):
            payload = self._get("/api/v1/prices", params={"symbols": ",".join(batch)})
            for row in _result_list(payload):
                symbol = str(row.get("symbol") or "").upper()
                if symbol:
                    prices[symbol] = row
        return prices

    def get_stocks(self, symbols: Iterable[str]) -> dict[str, dict[str, Any]]:
        clean_symbols = _clean_symbols(symbols)
        if not clean_symbols:
            return {}

        stocks: dict[str, dict[str, Any]] = {}
        for batch in _chunks(clean_symbols, 200):
            payload = self._get("/api/v1/stocks", params={"symbols": ",".join(batch)})
            for row in _result_list(payload):
                symbol = str(row.get("symbol") or "").upper()
                if symbol:
                    stocks[symbol] = row
        return stocks

    def get_candles(self, symbol: str, interval: str = "1d", count: int = 8) -> list[dict[str, Any]]:
        payload = self._get(
            "/api/v1/candles",
            params={
                "symbol": symbol.upper(),
                "interval": interval,
                "count": count,
                "adjusted": "true",
            },
        )
        result = payload.get("result")
        if not isinstance(result, dict):
            return []
        candles = result.get("candles")
        if not isinstance(candles, list):
            return []
        return [row for row in candles if isinstance(row, dict)]

    def get_us_snapshot(self, symbol: str, name: str | None = None, exchange: str | None = None) -> MarketSnapshot:
        symbol = symbol.upper()
        price_row = self.get_prices([symbol]).get(symbol)
        if not price_row:
            raise RuntimeError(f"Toss price not found for {symbol}")

        stock_row = self.get_stocks([symbol]).get(symbol, {})
        candles = self.get_candles(symbol, interval="1d", count=8)
        minute_candles = self.get_candles(symbol, interval="1m", count=200)
        usd_krw = self.get_usd_krw_rate()
        return build_us_snapshot_from_toss(
            symbol,
            price_row,
            stock_row,
            candles,
            usd_krw,
            name=name,
            exchange=exchange,
            minute_candles=minute_candles,
        )

    def get_usd_krw_rate(self) -> float:
        try:
            payload = self._get(
                "/api/v1/exchange-rate",
                params={"baseCurrency": "USD", "quoteCurrency": "KRW"},
            )
            result = payload.get("result")
            if isinstance(result, dict):
                return _to_float(result.get("rate") or result.get("midRate"), default=USD_KRW_FALLBACK)
        except Exception:
            return USD_KRW_FALLBACK
        return USD_KRW_FALLBACK

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        token = self.auth_client.get_access_token()
        response = self.http_client.get(
            f"{self.base_url}{path}",
            headers={"authorization": token.authorization},
            params=params,
        )
        if response.status_code in (401, 403):
            token = self.auth_client.get_access_token(force_refresh=True)
            response = self.http_client.get(
                f"{self.base_url}{path}",
                headers={"authorization": token.authorization},
                params=params,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Toss API request failed {path}: {response.status_code} {response.text}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Toss API response is not an object: {payload}")
        return payload


def build_us_snapshot_from_toss(
    symbol: str,
    price_row: dict[str, Any],
    stock_row: dict[str, Any],
    candles: list[dict[str, Any]],
    usd_krw: float,
    name: str | None = None,
    exchange: str | None = None,
    minute_candles: list[dict[str, Any]] | None = None,
) -> MarketSnapshot:
    sorted_candles = sorted(candles, key=lambda row: str(row.get("timestamp") or ""))
    latest = sorted_candles[-1] if sorted_candles else {}
    previous = sorted_candles[-2] if len(sorted_candles) >= 2 else {}
    previous_window = sorted_candles[:-1] if len(sorted_candles) >= 2 else []

    price = _to_float(price_row.get("lastPrice"))
    if price <= 0:
        price = _to_float(latest.get("closePrice"))
    if price <= 0:
        raise RuntimeError(f"Toss price returned zero for {symbol}")

    previous_close = _to_float(previous.get("closePrice"))
    open_price = _to_float(latest.get("openPrice"))
    high_price = _to_float(latest.get("highPrice"))
    low_price = _to_float(latest.get("lowPrice"))
    current_volume = _to_float(latest.get("volume"))
    avg_volume = _average([_to_float(row.get("volume")) for row in previous_window if _to_float(row.get("volume")) > 0])
    daily_volume_ratio = current_volume / avg_volume if current_volume > 0 and avg_volume > 0 else 1.0
    minute_volume_ratio = _minute_volume_ratio(minute_candles or [])
    volume_ratio = max(daily_volume_ratio, minute_volume_ratio)

    if previous_close > 0:
        change_pct = ((price - previous_close) / previous_close) * 100
    elif open_price > 0:
        change_pct = ((price - open_price) / open_price) * 100
    else:
        change_pct = 0.0

    market = str(stock_row.get("market") or exchange or "").upper() or None
    resolved_name = name or stock_row.get("englishName") or stock_row.get("name") or symbol
    minute_volume = _recent_minute_volume(minute_candles or [], window=30)
    reference_volume = max(current_volume, minute_volume)
    trading_value_krw = price * reference_volume * usd_krw if reference_volume > 0 else 0.0
    vwap_price = _typical_price(high_price, low_price, price)

    return MarketSnapshot(
        symbol=symbol.upper(),
        name=str(resolved_name),
        market="US",
        price=price,
        change_pct=change_pct,
        volume_ratio=volume_ratio,
        trading_value_krw=trading_value_krw,
        open_price=open_price or None,
        high_price=high_price or None,
        low_price=low_price or None,
        vwap_price=vwap_price,
        exchange=_to_kis_exchange(market),
    )


def _result_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result")
    if not isinstance(result, list):
        return []
    return [row for row in result if isinstance(row, dict)]


def _clean_symbols(symbols: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    clean: list[str] = []
    for symbol in symbols:
        value = str(symbol).strip().upper()
        if not value or value in seen:
            continue
        seen.add(value)
        clean.append(value)
    return clean


def _chunks(items: list[str], size: int):
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return default


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _minute_volume_ratio(candles: list[dict[str, Any]], window: int = 10) -> float:
    sorted_candles = sorted(candles, key=lambda row: str(row.get("timestamp") or ""))
    if len(sorted_candles) < window * 3:
        return 1.0

    volumes = [_to_float(row.get("volume")) for row in sorted_candles]
    recent = sum(volumes[-window:])
    previous = volumes[: -window]
    previous_windows = [
        sum(previous[idx : idx + window])
        for idx in range(0, len(previous) - window + 1, window)
    ]
    average_window_volume = _average([value for value in previous_windows if value > 0])
    if recent <= 0 or average_window_volume <= 0:
        return 1.0
    return recent / average_window_volume


def _recent_minute_volume(candles: list[dict[str, Any]], window: int) -> float:
    sorted_candles = sorted(candles, key=lambda row: str(row.get("timestamp") or ""))
    if not sorted_candles:
        return 0.0
    return sum(_to_float(row.get("volume")) for row in sorted_candles[-window:])


def _typical_price(high_price: float, low_price: float, close_price: float) -> float | None:
    if high_price > 0 and low_price > 0 and close_price > 0:
        return (high_price + low_price + close_price) / 3
    return None


def _to_kis_exchange(market: str | None) -> str | None:
    if market == "NASDAQ":
        return "NAS"
    if market == "NYSE":
        return "NYS"
    if market == "AMEX":
        return "AMS"
    return market
