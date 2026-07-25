from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from typing import Any

import httpx

from app.brokers.kis_auth import KisAuthClient


KIS_EXPIRED_TOKEN_CODE = "EGW00123"
KIS_RATE_LIMIT_CODE = "EGW00201"
KIS_RATE_LIMIT_MAX_RETRIES = 2
KIS_RATE_LIMIT_RETRY_DELAY_SECONDS = 1.2
USD_KRW_FALLBACK = 1350.0
KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class PriceSnapshot:
    symbol: str
    name: str
    market: str
    price: float
    change_pct: float
    trading_value_krw: float
    exchange: str | None = None
    cumulative_volume: float = 0.0


@dataclass(frozen=True)
class MinuteBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    trading_value: float = 0.0


@dataclass(frozen=True)
class OrderRequest:
    market: str
    side: str
    symbol: str
    quantity: int
    price: float
    order_type: str = "limit"
    exchange: str | None = None
    session: str = "regular"


@dataclass(frozen=True)
class OrderResult:
    market: str
    side: str
    symbol: str
    quantity: int
    price: float
    session: str
    order_no: str | None
    order_org_no: str | None
    message: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class CancelResult:
    market: str
    symbol: str
    original_order_no: str
    cancel_order_no: str | None
    message: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class OrderFillStatus:
    state: str
    filled_quantity: float
    average_price: float
    raw: dict[str, Any]


@dataclass(frozen=True)
class BrokerHolding:
    symbol: str
    name: str
    market: str
    quantity: float
    average_price: float
    current_price: float
    exchange: str | None = None


class KisClient:
    def __init__(
        self,
        app_key: str | None,
        app_secret: str | None,
        account_no: str | None = None,
        account_product_code: str | None = None,
        env: str = "paper",
        token_cache_path: str = "data/kis_token_paper.json",
        http_client: httpx.Client | None = None,
    ) -> None:
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        self.account_product_code = account_product_code
        self.env = env.strip().lower()
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

    def assert_readonly_paper_mode(self, paper_trading_only: bool, real_trading_enabled: bool) -> None:
        self.auth.assert_paper_mode(
            paper_trading_only=paper_trading_only,
            real_trading_enabled=real_trading_enabled,
        )

    def get_domestic_balance_raw(self) -> dict[str, Any]:
        if not self.account_no or not self.account_product_code:
            raise ValueError("KIS_ACCOUNT_NO and KIS_ACCOUNT_PRODUCT_CODE are required.")

        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id="VTTC8434R",
            params={
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_product_code,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            },
        )
        return _checked_payload(response, "KIS domestic balance request failed")

    def get_overseas_balance_raw(self) -> dict[str, Any]:
        self._require_account()
        response = self._get_with_auth_retry(
            "/uapi/overseas-stock/v1/trading/inquire-balance",
            tr_id="VTTS3012R" if self.env == "paper" else "TTTS3012R",
            params={
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_product_code,
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": "",
            },
        )
        return _checked_payload(response, "KIS overseas balance request failed")

    def get_holdings(self, market: str) -> list[BrokerHolding]:
        normalized_market = market.strip().upper()
        if normalized_market == "KR":
            payload = self.get_domestic_balance_raw()
            return [
                _domestic_output_to_holding(item)
                for item in _dict_list(payload.get("output1"))
                if _to_float(item.get("hldg_qty")) > 0
            ]
        if normalized_market == "US":
            payload = self.get_overseas_balance_raw()
            return [
                _overseas_output_to_holding(item)
                for item in _dict_list(payload.get("output1"))
                if _to_float(item.get("ovrs_cblc_qty")) > 0
            ]
        raise ValueError("market must be KR or US.")

    def get_order_fill_status(
        self,
        *,
        market: str,
        order_no: str,
        symbol: str,
        quantity: float,
        submitted_at: datetime,
    ) -> OrderFillStatus:
        normalized_market = market.strip().upper()
        if normalized_market == "KR":
            rows = self._get_domestic_order_rows(order_no, symbol, submitted_at)
            return _domestic_row_to_fill_status(_find_order_row(rows, order_no, symbol), quantity)
        if normalized_market == "US":
            rows = self._get_overseas_order_rows(submitted_at)
            return _overseas_row_to_fill_status(_find_order_row(rows, order_no, symbol), quantity)
        raise ValueError("market must be KR or US.")

    def _get_domestic_order_rows(
        self,
        order_no: str,
        symbol: str,
        submitted_at: datetime,
    ) -> list[dict[str, Any]]:
        self._require_account()
        order_date = _as_kst(submitted_at).strftime("%Y%m%d")
        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            tr_id="VTTC0081R" if self.env == "paper" else "TTTC0081R",
            params={
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_product_code,
                "INQR_STRT_DT": order_date,
                "INQR_END_DT": order_date,
                "SLL_BUY_DVSN_CD": "00",
                "PDNO": symbol,
                "CCLD_DVSN": "00",
                "INQR_DVSN": "00",
                "INQR_DVSN_3": "00",
                "ORD_GNO_BRNO": "",
                "ODNO": order_no,
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
                "EXCG_ID_DVSN_CD": "ALL",
            },
        )
        payload = _checked_payload(response, "KIS domestic fill inquiry failed")
        return _dict_list(payload.get("output1"))

    def _get_overseas_order_rows(self, submitted_at: datetime) -> list[dict[str, Any]]:
        self._require_account()
        order_date = _as_kst(submitted_at).strftime("%Y%m%d")
        response = self._get_with_auth_retry(
            "/uapi/overseas-stock/v1/trading/inquire-ccnl",
            tr_id="VTTS3035R" if self.env == "paper" else "TTTS3035R",
            params={
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_product_code,
                "PDNO": "" if self.env == "paper" else "%",
                "ORD_STRT_DT": order_date,
                "ORD_END_DT": order_date,
                "SLL_BUY_DVSN": "00",
                "CCLD_NCCS_DVSN": "00",
                "OVRS_EXCG_CD": "" if self.env == "paper" else "NASD",
                "SORT_SQN": "DS",
                "ORD_DT": "",
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "CTX_AREA_NK200": "",
                "CTX_AREA_FK200": "",
            },
        )
        payload = _checked_payload(response, "KIS overseas fill inquiry failed")
        return _dict_list(payload.get("output"))

    def get_domestic_price(self, symbol: str, name: str | None = None) -> PriceSnapshot:
        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
        )
        payload = _checked_payload(response, "KIS domestic price request failed")
        return _domestic_output_to_snapshot(symbol, name, payload.get("output") or {})

    def get_overseas_price(self, symbol: str, exchange: str = "NAS", name: str | None = None) -> PriceSnapshot:
        response = self._get_with_auth_retry(
            "/uapi/overseas-price/v1/quotations/price",
            tr_id="HHDFS00000300",
            params={
                "AUTH": "",
                "EXCD": exchange,
                "SYMB": symbol,
            },
        )
        payload = _checked_payload(response, "KIS overseas price request failed")
        snapshot = _overseas_output_to_snapshot(symbol, exchange, name, payload.get("output") or {})
        if snapshot.price <= 0:
            raise RuntimeError(f"KIS overseas price returned zero price: {exchange}:{symbol}")
        return snapshot

    def get_domestic_minute_bars(self, symbol: str, limit: int = 30) -> list[MinuteBar]:
        response = self._get_with_auth_retry(
            "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
            tr_id="FHKST03010200",
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
                "FID_INPUT_HOUR_1": datetime.now(KST).strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_ETC_CLS_CODE": "",
            },
        )
        payload = _checked_payload(response, "KIS domestic minute chart request failed")
        bars = [_domestic_output_to_minute_bar(item) for item in payload.get("output2") or []]
        return _sorted_valid_bars(bars, limit)

    def get_overseas_minute_bars(
        self,
        symbol: str,
        exchange: str = "NAS",
        limit: int = 20,
    ) -> list[MinuteBar]:
        response = self._get_with_auth_retry(
            "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice",
            tr_id="HHDFS76950200",
            params={
                "AUTH": "",
                "EXCD": exchange,
                "SYMB": symbol,
                "NMIN": "1",
                "PINC": "1",
                "NEXT": "",
                "NREC": str(max(8, min(limit, 120))),
                "FILL": "",
                "KEYB": "",
            },
        )
        payload = _checked_payload(response, "KIS overseas minute chart request failed")
        bars = [_overseas_output_to_minute_bar(item) for item in payload.get("output2") or []]
        return _sorted_valid_bars(bars, limit)

    def place_domestic_order(
        self,
        *,
        side: str,
        symbol: str,
        quantity: int,
        price: int,
        order_type: str = "limit",
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> OrderResult:
        self._assert_order_allowed(order_enabled, paper_trading_only, real_trading_enabled)
        normalized_side = _normalize_side(side)
        payload = self._build_domestic_order_payload(
            side=normalized_side,
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
        )
        tr_id = "VTTC0802U" if normalized_side == "buy" else "VTTC0801U"
        response = self._post_with_auth_retry(
            "/uapi/domestic-stock/v1/trading/order-cash",
            tr_id=tr_id,
            payload=payload,
        )
        checked = _checked_payload(response, "KIS domestic order request failed")
        return _order_payload_to_result("KR", normalized_side, symbol, quantity, price, "regular", checked)

    def place_overseas_order(
        self,
        *,
        side: str,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str = "NAS",
        order_type: str = "limit",
        session: str = "regular",
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> OrderResult:
        self._assert_order_allowed(order_enabled, paper_trading_only, real_trading_enabled)
        normalized_side = _normalize_side(side)
        normalized_session = _normalize_overseas_session(session)
        if normalized_session != "regular" and _normalize_order_type(order_type) == "market":
            raise ValueError("US day/pre/after session orders must use limit order_type.")
        payload = self._build_overseas_order_payload(
            symbol=symbol,
            quantity=quantity,
            price=price,
            exchange=exchange,
            order_type=order_type,
            session=normalized_session,
        )
        tr_id = _overseas_order_tr_id(normalized_side, normalized_session)
        path = _overseas_order_path(normalized_session)
        response = self._post_with_auth_retry(
            path,
            tr_id=tr_id,
            payload=payload,
        )
        checked = _checked_payload(response, "KIS overseas order request failed")
        return _order_payload_to_result("US", normalized_side, symbol, quantity, price, normalized_session, checked)

    def cancel_order(
        self,
        *,
        market: str,
        symbol: str,
        order_no: str,
        quantity: int,
        requested_price: float,
        order_org_no: str | None = None,
        exchange: str | None = None,
        session: str = "regular",
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> CancelResult:
        self._assert_order_allowed(order_enabled, paper_trading_only, real_trading_enabled)
        self._require_account()
        normalized_market = market.strip().upper()
        if normalized_market == "KR":
            if not order_org_no:
                raise ValueError("Domestic cancellation requires the original order organization number.")
            payload = {
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_product_code,
                "KRX_FWDG_ORD_ORGNO": order_org_no,
                "ORGN_ODNO": order_no,
                "ORD_DVSN": "00",
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": str(_positive_int(quantity, "quantity")),
                "ORD_UNPR": str(int(_non_negative_float(requested_price, "requested_price"))),
                "QTY_ALL_ORD_YN": "Y",
                "EXCG_ID_DVSN_CD": "KRX",
            }
            response = self._post_with_auth_retry(
                "/uapi/domestic-stock/v1/trading/order-rvsecncl",
                tr_id="VTTC0013U" if self.env == "paper" else "TTTC0013U",
                payload=payload,
            )
            checked = _checked_payload(response, "KIS domestic cancellation request failed")
            return _cancel_payload_to_result("KR", symbol, order_no, checked)
        if normalized_market == "US":
            normalized_session = _normalize_overseas_session(session)
            if normalized_session == "day":
                raise RuntimeError("KIS paper daytime cancellation is not documented and is disabled.")
            payload = {
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_product_code,
                "OVRS_EXCG_CD": _overseas_order_exchange_code(exchange or "NAS"),
                "PDNO": symbol.strip().upper(),
                "ORGN_ODNO": order_no,
                "RVSE_CNCL_DVSN_CD": "02",
                "ORD_QTY": str(_positive_int(quantity, "quantity")),
                "OVRS_ORD_UNPR": "0",
                "MGCO_APTM_ODNO": "",
                "ORD_SVR_DVSN_CD": "0",
            }
            response = self._post_with_auth_retry(
                "/uapi/overseas-stock/v1/trading/order-rvsecncl",
                tr_id="VTTT1004U" if self.env == "paper" else "TTTT1004U",
                payload=payload,
            )
            checked = _checked_payload(response, "KIS overseas cancellation request failed")
            return _cancel_payload_to_result("US", symbol, order_no, checked)
        raise ValueError("market must be KR or US.")

    def build_order_request(
        self,
        *,
        market: str,
        side: str,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str | None = None,
        order_type: str = "limit",
        session: str = "regular",
    ) -> OrderRequest:
        normalized_market = market.strip().upper()
        if normalized_market not in {"KR", "US"}:
            raise ValueError("market must be KR or US.")
        normalized_session = "regular" if normalized_market == "KR" else _normalize_overseas_session(session)
        return OrderRequest(
            market=normalized_market,
            side=_normalize_side(side),
            symbol=symbol.strip().upper(),
            quantity=_positive_int(quantity, "quantity"),
            price=_non_negative_float(price, "price"),
            exchange=exchange,
            order_type=_normalize_order_type(order_type),
            session=normalized_session,
        )

    def _get_with_auth_retry(self, path: str, tr_id: str, params: dict[str, Any]) -> httpx.Response:
        response = self._get_with_auth(path, tr_id=tr_id, params=params, force_refresh=False)
        if _is_expired_token_response(response):
            response = self._get_with_auth(path, tr_id=tr_id, params=params, force_refresh=True)
        for _ in range(KIS_RATE_LIMIT_MAX_RETRIES):
            if not _is_rate_limit_response(response):
                break
            time.sleep(KIS_RATE_LIMIT_RETRY_DELAY_SECONDS)
            response = self._get_with_auth(path, tr_id=tr_id, params=params, force_refresh=False)
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
                "custtype": "P",
            },
            params=params,
        )

    def _post_with_auth_retry(self, path: str, tr_id: str, payload: dict[str, Any]) -> httpx.Response:
        response = self._post_with_auth(path, tr_id=tr_id, payload=payload, force_refresh=False)
        if _is_expired_token_response(response):
            response = self._post_with_auth(path, tr_id=tr_id, payload=payload, force_refresh=True)
        for _ in range(KIS_RATE_LIMIT_MAX_RETRIES):
            if not _is_rate_limit_response(response):
                break
            time.sleep(KIS_RATE_LIMIT_RETRY_DELAY_SECONDS)
            response = self._post_with_auth(path, tr_id=tr_id, payload=payload, force_refresh=False)
        return response

    def _post_with_auth(
        self,
        path: str,
        tr_id: str,
        payload: dict[str, Any],
        force_refresh: bool,
    ) -> httpx.Response:
        token = self.auth.get_access_token(force_refresh=force_refresh)
        hashkey = self.auth.make_hashkey(payload)
        return self.http_client.post(
            f"{self.base_url}{path}",
            headers={
                "content-type": "application/json; charset=utf-8",
                "authorization": token.authorization,
                "appkey": self.app_key or "",
                "appsecret": self.app_secret or "",
                "tr_id": tr_id,
                "custtype": "P",
                "hashkey": hashkey,
            },
            json=payload,
        )

    def _assert_order_allowed(
        self,
        order_enabled: bool,
        paper_trading_only: bool,
        real_trading_enabled: bool,
    ) -> None:
        if not order_enabled:
            raise RuntimeError("ORDER_ENABLED must be true before placing orders.")
        self.assert_readonly_paper_mode(
            paper_trading_only=paper_trading_only,
            real_trading_enabled=real_trading_enabled,
        )

    def _require_account(self) -> None:
        if not self.account_no or not self.account_product_code:
            raise ValueError("KIS_ACCOUNT_NO and KIS_ACCOUNT_PRODUCT_CODE are required.")

    def _build_domestic_order_payload(
        self,
        *,
        side: str,
        symbol: str,
        quantity: int,
        price: int,
        order_type: str,
    ) -> dict[str, str]:
        if not self.account_no or not self.account_product_code:
            raise ValueError("KIS_ACCOUNT_NO and KIS_ACCOUNT_PRODUCT_CODE are required.")
        return {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_product_code,
            "PDNO": symbol.strip(),
            "ORD_DVSN": _domestic_order_type_code(order_type),
            "ORD_QTY": str(_positive_int(quantity, "quantity")),
            "ORD_UNPR": str(int(_non_negative_float(price, "price"))),
        }

    def _build_overseas_order_payload(
        self,
        *,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str,
        order_type: str,
        session: str = "regular",
    ) -> dict[str, str]:
        if not self.account_no or not self.account_product_code:
            raise ValueError("KIS_ACCOUNT_NO and KIS_ACCOUNT_PRODUCT_CODE are required.")
        payload = {
            "CANO": self.account_no,
            "ACNT_PRDT_CD": self.account_product_code,
            "OVRS_EXCG_CD": _overseas_order_exchange_code(exchange),
            "PDNO": symbol.strip().upper(),
            "ORD_QTY": str(_positive_int(quantity, "quantity")),
            "OVRS_ORD_UNPR": _format_overseas_price(price, order_type),
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": _overseas_order_type_code(order_type),
        }
        if _normalize_overseas_session(session) == "day":
            payload["CTAC_TLNO"] = " "
            payload["MGCO_APTM_ODNO"] = ""
        return payload


def summarize_domestic_balance(payload: dict[str, Any]) -> dict[str, Any]:
    holdings = payload.get("output1") or []
    summary = _first_dict(payload.get("output2"))
    return {
        "holdings_count": len(holdings) if isinstance(holdings, list) else 0,
        "cash_krw": _to_float(summary.get("dnca_tot_amt") or summary.get("nass_amt")),
        "total_eval_krw": _to_float(summary.get("tot_evlu_amt")),
        "purchase_amount_krw": _to_float(summary.get("pchs_amt_smtl_amt")),
        "profit_loss_krw": _to_float(summary.get("evlu_pfls_smtl_amt")),
        "profit_loss_pct": _to_float(summary.get("evlu_pfls_rt")),
    }


def _domestic_row_to_fill_status(row: dict[str, Any], expected_quantity: float) -> OrderFillStatus:
    if not row:
        return OrderFillStatus("UNKNOWN", 0.0, 0.0, {})
    ordered = _to_float(row.get("ord_qty")) or expected_quantity
    filled = _to_float(row.get("tot_ccld_qty"))
    average_price = _to_float(row.get("avg_prvs"))
    canceled = str(row.get("cncl_yn") or "").strip().upper() == "Y"
    rejected = _to_float(row.get("rjct_qty")) > 0
    return OrderFillStatus(
        state=_fill_state(ordered, filled, canceled=canceled, rejected=rejected),
        filled_quantity=filled,
        average_price=average_price,
        raw=row,
    )


def _overseas_row_to_fill_status(row: dict[str, Any], expected_quantity: float) -> OrderFillStatus:
    if not row:
        return OrderFillStatus("UNKNOWN", 0.0, 0.0, {})
    ordered = _to_float(row.get("ft_ord_qty")) or expected_quantity
    filled = _to_float(row.get("ft_ccld_qty"))
    average_price = _to_float(row.get("ft_ccld_unpr3"))
    canceled = _to_float(row.get("nccs_qty")) <= 0 and filled < ordered
    rejected = str(row.get("rjct_rson") or row.get("rjct_rson_name") or "").strip() != ""
    return OrderFillStatus(
        state=_fill_state(ordered, filled, canceled=canceled, rejected=rejected),
        filled_quantity=filled,
        average_price=average_price,
        raw=row,
    )


def _fill_state(ordered: float, filled: float, *, canceled: bool, rejected: bool) -> str:
    if ordered > 0 and filled >= ordered:
        return "FILLED"
    if canceled and filled > 0:
        return "PARTIAL_CANCELED"
    if filled > 0:
        return "PARTIAL"
    if rejected:
        return "REJECTED"
    if canceled:
        return "CANCELED"
    return "PENDING"


def _find_order_row(rows: list[dict[str, Any]], order_no: str, symbol: str) -> dict[str, Any]:
    normalized_symbol = symbol.strip().upper()
    for row in rows:
        row_order_no = str(row.get("odno") or row.get("ODNO") or "")
        row_symbol = str(row.get("pdno") or row.get("ovrs_pdno") or "").strip().upper()
        if _same_order_no(row_order_no, order_no) and (not row_symbol or row_symbol == normalized_symbol):
            return row
    return {}


def _same_order_no(left: str, right: str) -> bool:
    return left.strip().lstrip("0") == right.strip().lstrip("0")


def _domestic_output_to_holding(output: dict[str, Any]) -> BrokerHolding:
    symbol = str(output.get("pdno") or "").strip()
    return BrokerHolding(
        symbol=symbol,
        name=str(output.get("prdt_name") or symbol),
        market="KR",
        quantity=_to_float(output.get("hldg_qty")),
        average_price=_to_float(output.get("pchs_avg_pric")),
        current_price=_to_float(output.get("prpr")),
        exchange="KRX",
    )


def _overseas_output_to_holding(output: dict[str, Any]) -> BrokerHolding:
    symbol = str(output.get("ovrs_pdno") or output.get("pdno") or "").strip().upper()
    return BrokerHolding(
        symbol=symbol,
        name=str(output.get("ovrs_item_name") or output.get("prdt_name") or symbol),
        market="US",
        quantity=_to_float(output.get("ovrs_cblc_qty")),
        average_price=_to_float(output.get("pchs_avg_pric")),
        current_price=_to_float(output.get("now_pric2")),
        exchange=_quote_exchange_code(str(output.get("ovrs_excg_cd") or "NASD")),
    )


def _quote_exchange_code(value: str) -> str:
    normalized = value.strip().upper()
    return {
        "NASD": "NAS",
        "NAS": "NAS",
        "NASDAQ": "NAS",
        "NYSE": "NYS",
        "NYS": "NYS",
        "AMEX": "AMS",
        "AMS": "AMS",
    }.get(normalized, "NAS")


def _as_kst(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=KST)
    return value.astimezone(KST)


def _order_payload_to_result(
    market: str,
    side: str,
    symbol: str,
    quantity: int,
    price: float,
    session: str,
    payload: dict[str, Any],
) -> OrderResult:
    output = _first_dict(payload.get("output"))
    order_no = output.get("ODNO") or output.get("odno")
    order_org_no = (
        output.get("KRX_FWDG_ORD_ORGNO")
        or output.get("krx_fwdg_ord_orgno")
        or output.get("ORD_GNO_BRNO")
        or output.get("ord_gno_brno")
    )
    return OrderResult(
        market=market,
        side=side,
        symbol=symbol,
        quantity=quantity,
        price=price,
        session=session,
        order_no=str(order_no) if order_no else None,
        order_org_no=str(order_org_no) if order_org_no else None,
        message=str(payload.get("msg1") or "order accepted"),
        raw=payload,
    )


def _cancel_payload_to_result(
    market: str,
    symbol: str,
    original_order_no: str,
    payload: dict[str, Any],
) -> CancelResult:
    output = _first_dict(payload.get("output"))
    cancel_order_no = output.get("ODNO") or output.get("odno")
    return CancelResult(
        market=market,
        symbol=symbol,
        original_order_no=original_order_no,
        cancel_order_no=str(cancel_order_no) if cancel_order_no else None,
        message=str(payload.get("msg1") or "cancellation accepted"),
        raw=payload,
    )


def _checked_payload(response: httpx.Response, message: str) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(f"{message}: {response.status_code} {response.text}")

    payload = response.json()
    if str(payload.get("rt_cd")) not in ("0", "None"):
        raise RuntimeError(f"{message}: {payload.get('msg1') or payload}")
    return payload


def _normalize_side(side: str) -> str:
    normalized = side.strip().lower()
    if normalized in {"buy", "bid"}:
        return "buy"
    if normalized in {"sell", "ask"}:
        return "sell"
    raise ValueError("side must be buy or sell.")


def _normalize_order_type(order_type: str) -> str:
    normalized = order_type.strip().lower()
    if normalized in {"limit", "market"}:
        return normalized
    raise ValueError("order_type must be limit or market.")


def _domestic_order_type_code(order_type: str) -> str:
    normalized = _normalize_order_type(order_type)
    if normalized == "market":
        return "01"
    return "00"


def _overseas_order_type_code(order_type: str) -> str:
    _normalize_order_type(order_type)
    return "00"


def _overseas_order_tr_id(side: str, session: str) -> str:
    normalized_side = _normalize_side(side)
    normalized_session = _normalize_overseas_session(session)
    if normalized_session == "day":
        return "VTTT6036U" if normalized_side == "buy" else "VTTT6037U"
    return "VTTT1002U" if normalized_side == "buy" else "VTTT1001U"


def _normalize_overseas_session(session: str) -> str:
    normalized = session.strip().lower()
    aliases = {
        "regular": "regular",
        "rth": "regular",
        "normal": "regular",
        "day": "day",
        "daytime": "day",
        "day-market": "day",
        "pre": "pre",
        "premarket": "pre",
        "pre-market": "pre",
        "after": "after",
        "aftermarket": "after",
        "after-market": "after",
    }
    if normalized not in aliases:
        raise ValueError("session must be one of regular, day, pre, after.")
    return aliases[normalized]


def _overseas_order_path(session: str) -> str:
    normalized = _normalize_overseas_session(session)
    if normalized == "day":
        return "/uapi/overseas-stock/v1/trading/daytime-order"
    return "/uapi/overseas-stock/v1/trading/order"


def _overseas_order_exchange_code(exchange: str) -> str:
    normalized = exchange.strip().upper()
    aliases = {
        "NAS": "NASD",
        "NASDAQ": "NASD",
        "NASD": "NASD",
        "NYS": "NYSE",
        "NYSE": "NYSE",
        "AMS": "AMEX",
        "AMEX": "AMEX",
        "ASE": "AMEX",
    }
    if normalized not in aliases:
        raise ValueError("exchange must be one of NAS, NASD, NYS, NYSE, AMS, AMEX, ASE.")
    return aliases[normalized]


def _format_overseas_price(price: float, order_type: str) -> str:
    if _normalize_order_type(order_type) == "market":
        return "0"
    normalized = _non_negative_float(price, "price")
    if normalized <= 0:
        raise ValueError("price must be greater than zero for limit orders.")
    return f"{normalized:.2f}"


def _positive_int(value: int, field_name: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a positive integer.") from exc
    if number <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return number


def _non_negative_float(value: float, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a non-negative number.") from exc
    if number < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")
    return number


def _domestic_output_to_snapshot(symbol: str, name: str | None, output: dict[str, Any]) -> PriceSnapshot:
    price = _to_float(output.get("stck_prpr"))
    volume = _to_float(output.get("acml_vol"))
    trading_value = _to_float(output.get("acml_tr_pbmn"))
    if trading_value <= 0 and volume > 0 and price > 0:
        trading_value = volume * price

    return PriceSnapshot(
        symbol=symbol,
        name=name or output.get("hts_kor_isnm") or symbol,
        market="KR",
        price=price,
        change_pct=_to_float(output.get("prdy_ctrt")),
        trading_value_krw=trading_value,
        cumulative_volume=volume,
    )


def _overseas_output_to_snapshot(
    symbol: str,
    exchange: str,
    name: str | None,
    output: dict[str, Any],
) -> PriceSnapshot:
    price = _to_float(output.get("last"))
    volume = _to_float(output.get("tvol"))
    trading_value_usd = _to_float(output.get("tamt"))
    if trading_value_usd <= 0 and volume > 0 and price > 0:
        trading_value_usd = volume * price

    return PriceSnapshot(
        symbol=symbol,
        name=name or output.get("name") or output.get("ename") or symbol,
        market="US",
        price=price,
        change_pct=_to_float(output.get("rate")),
        trading_value_krw=trading_value_usd * USD_KRW_FALLBACK,
        exchange=exchange,
        cumulative_volume=volume,
    )


def _domestic_output_to_minute_bar(output: dict[str, Any]) -> MinuteBar:
    return MinuteBar(
        timestamp=f"{output.get('stck_bsop_date') or ''}{output.get('stck_cntg_hour') or ''}",
        open=_to_float(output.get("stck_oprc")),
        high=_to_float(output.get("stck_hgpr")),
        low=_to_float(output.get("stck_lwpr")),
        close=_to_float(output.get("stck_prpr")),
        volume=_to_float(output.get("cntg_vol")),
        trading_value=_to_float(output.get("acml_tr_pbmn")),
    )


def _overseas_output_to_minute_bar(output: dict[str, Any]) -> MinuteBar:
    return MinuteBar(
        timestamp=f"{output.get('xymd') or output.get('kymd') or ''}{output.get('xhms') or output.get('khms') or ''}",
        open=_to_float(output.get("open")),
        high=_to_float(output.get("high")),
        low=_to_float(output.get("low")),
        close=_to_float(output.get("last")),
        volume=_to_float(output.get("evol")),
        trading_value=_to_float(output.get("eamt")),
    )


def _sorted_valid_bars(bars: list[MinuteBar], limit: int) -> list[MinuteBar]:
    valid = [bar for bar in bars if bar.close > 0 and bar.volume >= 0]
    ordered = sorted(valid, key=lambda bar: bar.timestamp)
    return ordered[-max(limit, 1) :]


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


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


def _is_rate_limit_response(response: httpx.Response) -> bool:
    try:
        payload = response.json()
    except ValueError:
        return False
    message = str(payload.get("msg1") or payload.get("message") or "")
    return payload.get("msg_cd") == KIS_RATE_LIMIT_CODE or "초당 거래건수" in message


def _is_expired_token_response(response: httpx.Response) -> bool:
    try:
        payload = response.json()
    except ValueError:
        return False
    message = str(payload.get("msg1") or "")
    return payload.get("msg_cd") == KIS_EXPIRED_TOKEN_CODE or "기간이 만료된 token" in message
