import json

import httpx

from app.brokers.kis_client import KisClient


def test_get_domestic_price_maps_kis_output(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200,
                json={
                    "access_token": "sample-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/uapi/domestic-stock/v1/quotations/inquire-price":
            assert request.headers["tr_id"] == "FHKST01010100"
            assert request.url.params["FID_COND_MRKT_DIV_CODE"] == "J"
            assert request.url.params["FID_INPUT_ISCD"] == "005930"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상처리 되었습니다.",
                    "output": {
                        "hts_kor_isnm": "삼성전자",
                        "stck_prpr": "78500",
                        "prdy_ctrt": "1.23",
                        "acml_vol": "1234567",
                        "acml_tr_pbmn": "96913509500",
                    },
                },
            )
        return httpx.Response(404, json={"path": request.url.path})

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    snapshot = client.get_domestic_price("005930")

    assert snapshot.symbol == "005930"
    assert snapshot.name == "삼성전자"
    assert snapshot.price == 78500
    assert snapshot.change_pct == 1.23
    assert snapshot.trading_value_krw == 96913509500


def test_get_overseas_price_maps_kis_output(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200,
                json={
                    "access_token": "sample-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/uapi/overseas-price/v1/quotations/price":
            assert request.headers["tr_id"] == "HHDFS00000300"
            assert request.url.params["EXCD"] == "NAS"
            assert request.url.params["SYMB"] == "NVDA"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "msg1": "정상처리 되었습니다.",
                    "output": {
                        "last": "144.20",
                        "rate": "5.60",
                        "tvol": "1000000",
                        "tamt": "144200000",
                    },
                },
            )
        return httpx.Response(404, json={"path": request.url.path})

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    snapshot = client.get_overseas_price("NVDA", exchange="NAS", name="NVIDIA")

    assert snapshot.symbol == "NVDA"
    assert snapshot.name == "NVIDIA"
    assert snapshot.price == 144.2
    assert snapshot.change_pct == 5.6
    assert snapshot.trading_value_krw == 144200000 * 1_350
    assert snapshot.exchange == "NAS"


def test_get_overseas_price_rejects_zero_price(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200,
                json={
                    "access_token": "sample-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                },
            )
        if request.url.path == "/uapi/overseas-price/v1/quotations/price":
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": {
                        "last": "0",
                        "rate": "0",
                        "tvol": "0",
                        "tamt": "0",
                    },
                },
            )
        return httpx.Response(404, json={"path": request.url.path})

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.get_overseas_price("NVDA", exchange="NYS", name="NVIDIA")
    except RuntimeError as exc:
        assert "zero price" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_kis_client_refreshes_token_once_when_server_reports_expired_token(tmp_path):
    token_requests = 0
    quote_authorizations = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_requests
        if request.url.path == "/oauth2/tokenP":
            token_requests += 1
            access_token = "old-token" if token_requests == 1 else "fresh-token"
            return httpx.Response(200, json={"access_token": access_token, "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == "/uapi/domestic-stock/v1/quotations/inquire-price":
            quote_authorizations.append(request.headers["authorization"])
            if request.headers["authorization"] == "Bearer old-token":
                return httpx.Response(500, json={"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "기간이 만료된 token 입니다."})
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": {
                        "stck_prpr": "78500",
                        "prdy_ctrt": "1.23",
                        "acml_vol": "1000",
                        "acml_tr_pbmn": "78500000",
                    },
                },
            )
        return httpx.Response(404)

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    snapshot = client.get_domestic_price("005930")

    assert snapshot.price == 78500
    assert token_requests == 2
    assert quote_authorizations == ["Bearer old-token", "Bearer fresh-token"]


def test_get_overseas_volume_surge_raw(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == "/uapi/overseas-stock/v1/ranking/volume-surge":
            assert request.headers["tr_id"] == "HHDFS76270000"
            assert request.url.params["EXCD"] == "NAS"
            return httpx.Response(200, json={"rt_cd": "0", "output2": [{"symb": "NVDA"}]})
        return httpx.Response(404)

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert client.get_overseas_volume_surge_raw(exchange="NAS")["output2"] == [{"symb": "NVDA"}]
