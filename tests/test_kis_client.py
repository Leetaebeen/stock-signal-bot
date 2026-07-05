import httpx

from app.brokers.kis_client import KisClient, summarize_domestic_balance


def test_get_domestic_price_maps_kis_output(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "sample-access-token", "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == "/uapi/domestic-stock/v1/quotations/inquire-price":
            assert request.headers["tr_id"] == "FHKST01010100"
            assert request.url.params["FID_INPUT_ISCD"] == "005930"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": {
                        "hts_kor_isnm": "삼성전자",
                        "stck_prpr": "78500",
                        "prdy_ctrt": "1.23",
                        "acml_vol": "1234567",
                        "acml_tr_pbmn": "96913509500",
                    },
                },
            )
        return httpx.Response(404)

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
    assert snapshot.market == "KR"
    assert snapshot.price == 78500
    assert snapshot.change_pct == 1.23
    assert snapshot.trading_value_krw == 96913509500


def test_get_overseas_price_maps_kis_output(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "sample-access-token", "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == "/uapi/overseas-price/v1/quotations/price":
            assert request.headers["tr_id"] == "HHDFS00000300"
            assert request.url.params["EXCD"] == "NAS"
            assert request.url.params["SYMB"] == "NVDA"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": {
                        "last": "144.20",
                        "rate": "5.60",
                        "tvol": "1000000",
                        "tamt": "144200000",
                    },
                },
            )
        return httpx.Response(404)

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    snapshot = client.get_overseas_price("NVDA", exchange="NAS", name="NVIDIA")

    assert snapshot.symbol == "NVDA"
    assert snapshot.name == "NVIDIA"
    assert snapshot.market == "US"
    assert snapshot.price == 144.2
    assert snapshot.change_pct == 5.6
    assert snapshot.trading_value_krw == 144200000 * 1_350
    assert snapshot.exchange == "NAS"


def test_get_domestic_balance_uses_paper_tr_id_and_summarizes(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(200, json={"access_token": "token", "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == "/uapi/domestic-stock/v1/trading/inquire-balance":
            assert request.headers["tr_id"] == "VTTC8434R"
            assert request.url.params["CANO"] == "12345678"
            assert request.url.params["ACNT_PRDT_CD"] == "01"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output1": [{"pdno": "005930"}, {"pdno": "000660"}],
                    "output2": [
                        {
                            "dnca_tot_amt": "1000000",
                            "tot_evlu_amt": "2500000",
                            "pchs_amt_smtl_amt": "2000000",
                            "evlu_pfls_smtl_amt": "500000",
                            "evlu_pfls_rt": "25.0",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        account_no="12345678",
        account_product_code="01",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    summary = summarize_domestic_balance(client.get_domestic_balance_raw())

    assert summary["holdings_count"] == 2
    assert summary["cash_krw"] == 1_000_000
    assert summary["total_eval_krw"] == 2_500_000
    assert summary["profit_loss_pct"] == 25.0


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
            return httpx.Response(200, json={"rt_cd": "0", "output": {"stck_prpr": "78500"}})
        return httpx.Response(404)

    client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="paper",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    snapshot = client.get_domestic_price("005930")

    assert snapshot.price == 78500
    assert token_requests == 2
    assert quote_authorizations == ["Bearer old-token", "Bearer fresh-token"]
