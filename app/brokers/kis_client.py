from typing import Any

import httpx

from app.brokers.kis_auth import KisAuthClient
from app.models import MarketSnapshot

KIS_EXPIRED_TOKEN_CODE = "EGW00123"


class KisClient:
    def __init__(
        self,
        app_key: str | None,
        app_secret: str | None,
        account_no: str | None = None,
        env: str = "paper",
        token_cache_path: str = "data/kis_token.json",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        self.env = env
        self.http_client = http_client or httpx.Client(timeout=10)
        self.auth = KisAuthClient(
            app_key=app_key,
            app_secret=app_secret,
            env=env,
            token_cache_path=token_cache_path,
            http_client=self.http_client,
        )

    @property
    def base_url(self) -> str:
        return self.auth.base_url

    def get_domestic_price(self, symbol: str, name: str | None = None) -> MarketSnapshot:
        payload = self.get_domestic_price_raw(symbol)
        output = payload.get("output") or {}
        return _domestic_output_to_snapshot(symbol=symbol, name=name, output=output)

    def get_domestic_price_raw(self, symbol: str) -> dict[str, Any]:
        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS price request failed: {response.status_code} {response.text}")

        payload = response.json()
        if str(payload.get("rt_cd")) not in ("0", "None"):
            raise RuntimeError(f"KIS price request failed: {payload.get('msg1') or payload}")
        return payload

    def get_domestic_fluctuation_rank_raw(
        self,
        count: int = 50,
        market: str = "J",
        min_price: int = 1_000,
        max_price: int = 1_000_000,
        min_volume: int = 100_000,
        max_rate: int = 15,
    ) -> dict[str, Any]:
        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/ranking/fluctuation",
            tr_id="FHPST01700000",
            params={
                "fid_cond_mrkt_div_code": market,
                "fid_cond_scr_div_code": "20170",
                "fid_input_iscd": "0000",
                "fid_rank_sort_cls_code": "0",
                "fid_input_cnt_1": str(count),
                "fid_prc_cls_code": "0",
                "fid_input_price_1": str(min_price),
                "fid_input_price_2": str(max_price),
                "fid_vol_cnt": str(min_volume),
                "fid_trgt_cls_code": "0",
                "fid_trgt_exls_cls_code": "0",
                "fid_div_cls_code": "0",
                "fid_rsfl_rate1": "0",
                "fid_rsfl_rate2": str(max_rate),
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS fluctuation rank request failed: {response.status_code} {response.text}")

        payload = response.json()
        if str(payload.get("rt_cd")) not in ("0", "None"):
            raise RuntimeError(f"KIS fluctuation rank request failed: {payload.get('msg1') or payload}")
        return payload

    def get_domestic_volume_rank_raw(
        self,
        rank_type: str = "1",
        market: str = "J",
        min_price: int = 1_000,
        max_price: int = 1_000_000,
        min_volume: int = 100_000,
    ) -> dict[str, Any]:
        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            tr_id="FHPST01710000",
            params={
                "FID_COND_MRKT_DIV_CODE": market,
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "1",
                "FID_BLNG_CLS_CODE": rank_type,
                "FID_TRGT_CLS_CODE": "111111111",
                "FID_TRGT_EXLS_CLS_CODE": "1111111111",
                "FID_INPUT_PRICE_1": str(min_price),
                "FID_INPUT_PRICE_2": str(max_price),
                "FID_VOL_CNT": str(min_volume),
                "FID_INPUT_DATE_1": "",
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS volume rank request failed: {response.status_code} {response.text}")

        payload = response.json()
        if str(payload.get("rt_cd")) not in ("0", "None"):
            raise RuntimeError(f"KIS volume rank request failed: {payload.get('msg1') or payload}")
        return payload

    def get_overseas_price(self, symbol: str, exchange: str = "NAS", name: str | None = None) -> MarketSnapshot:
        payload = self.get_overseas_price_raw(symbol=symbol, exchange=exchange)
        output = payload.get("output") or {}
        snapshot = _overseas_output_to_snapshot(symbol=symbol, exchange=exchange, name=name, output=output)
        if snapshot.price <= 0:
            raise RuntimeError(f"KIS overseas price returned zero price: {exchange}:{symbol}")
        return snapshot

    def get_overseas_price_raw(self, symbol: str, exchange: str = "NAS") -> dict[str, Any]:
        response = self._get_with_auth_retry(
            "/uapi/overseas-price/v1/quotations/price",
            tr_id="HHDFS00000300",
            params={
                "AUTH": "",
                "EXCD": exchange,
                "SYMB": symbol,
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS overseas price request failed: {response.status_code} {response.text}")

        payload = response.json()
        if str(payload.get("rt_cd")) not in ("0", "None"):
            raise RuntimeError(f"KIS overseas price request failed: {payload.get('msg1') or payload}")
        return payload

    def get_overseas_volume_surge_raw(
        self,
        exchange: str = "NAS",
        minute_window: str = "4",
        volume_range: str = "3",
    ) -> dict[str, Any]:
        response = self._get_with_auth_retry(
            "/uapi/overseas-stock/v1/ranking/volume-surge",
            tr_id="HHDFS76270000",
            params={
                "EXCD": exchange,
                "MINX": minute_window,
                "VOL_RANG": volume_range,
                "KEYB": "",
                "AUTH": "",
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS overseas volume surge request failed: {response.status_code} {response.text}")
        payload = response.json()
        if str(payload.get("rt_cd")) not in ("0", "None"):
            raise RuntimeError(f"KIS overseas volume surge request failed: {payload.get('msg1') or payload}")
        return payload

    def get_overseas_volume_power_raw(
        self,
        exchange: str = "NAS",
        day_window: str = "0",
        volume_range: str = "3",
    ) -> dict[str, Any]:
        response = self._get_with_auth_retry(
            "/uapi/overseas-stock/v1/ranking/volume-power",
            tr_id="HHDFS76280000",
            params={
                "EXCD": exchange,
                "NDAY": day_window,
                "VOL_RANG": volume_range,
                "AUTH": "",
                "KEYB": "",
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(f"KIS overseas volume power request failed: {response.status_code} {response.text}")
        payload = response.json()
        if str(payload.get("rt_cd")) not in ("0", "None"):
            raise RuntimeError(f"KIS overseas volume power request failed: {payload.get('msg1') or payload}")
        return payload

    async def get_kr_snapshots(self) -> list[MarketSnapshot]:
        raise NotImplementedError("Full Korean market scan is not implemented yet.")

    async def get_us_snapshots(self) -> list[MarketSnapshot]:
        raise NotImplementedError("US market snapshots are not implemented yet.")

    def _get_with_auth_retry(self, path: str, tr_id: str, params: dict[str, Any]) -> httpx.Response:
        response = self._get_with_auth(path, tr_id=tr_id, params=params, force_refresh=False)
        if _is_expired_token_response(response):
            response = self._get_with_auth(path, tr_id=tr_id, params=params, force_refresh=True)
        return response

    def _get_with_auth(
        self,
        path: str,
        tr_id: str,
        params: dict[str, Any],
        force_refresh: bool,
    ) -> httpx.Response:
        token = self.auth.get_access_token(force_refresh=force_refresh)
        return self.http_client.get(
            f"{self.base_url}{path}",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": token.authorization,
                "appkey": self.app_key or "",
                "appsecret": self.app_secret or "",
                "tr_id": tr_id,
            },
            params=params,
        )


def _domestic_output_to_snapshot(symbol: str, name: str | None, output: dict[str, Any]) -> MarketSnapshot:
    stock_name = name or output.get("hts_kor_isnm") or symbol
    price = _to_float(output.get("stck_prpr"))
    change_pct = _to_float(output.get("prdy_ctrt"))
    volume = _to_float(output.get("acml_vol"))
    trading_value = _to_float(output.get("acml_tr_pbmn"))
    open_price = _to_float(output.get("stck_oprc"))
    high_price = _to_float(output.get("stck_hgpr"))
    low_price = _to_float(output.get("stck_lwpr"))
    if trading_value <= 0 and volume > 0 and price > 0:
        trading_value = volume * price
    vwap_price = trading_value / volume if trading_value > 0 and volume > 0 else None

    return MarketSnapshot(
        symbol=symbol,
        name=stock_name,
        market="KR",
        price=price,
        change_pct=change_pct,
        volume_ratio=1.0,
        trading_value_krw=trading_value,
        open_price=open_price or None,
        high_price=high_price or None,
        low_price=low_price or None,
        vwap_price=vwap_price,
    )


def _overseas_output_to_snapshot(
    symbol: str,
    exchange: str,
    name: str | None,
    output: dict[str, Any],
) -> MarketSnapshot:
    stock_name = name or output.get("name") or output.get("ename") or symbol
    price = _to_float(output.get("last"))
    change_pct = _to_float(output.get("rate"))
    volume = _to_float(output.get("tvol"))
    trading_value_usd = _to_float(output.get("tamt"))
    open_price = _to_float(output.get("open"))
    high_price = _to_float(output.get("high"))
    low_price = _to_float(output.get("low"))
    if trading_value_usd <= 0 and volume > 0 and price > 0:
        trading_value_usd = volume * price
    vwap_price = trading_value_usd / volume if trading_value_usd > 0 and volume > 0 else None

    return MarketSnapshot(
        symbol=symbol,
        name=stock_name,
        market="US",
        price=price,
        change_pct=change_pct,
        volume_ratio=1.0,
        trading_value_krw=trading_value_usd * 1_350,
        open_price=open_price or None,
        high_price=high_price or None,
        low_price=low_price or None,
        vwap_price=vwap_price,
        exchange=exchange,
    )


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _is_expired_token_response(response: httpx.Response) -> bool:
    try:
        payload = response.json()
    except ValueError:
        return False
    message = str(payload.get("msg1") or "")
    return payload.get("msg_cd") == KIS_EXPIRED_TOKEN_CODE or "기간이 만료된 token" in message
