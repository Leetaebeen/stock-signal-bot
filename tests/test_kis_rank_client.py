import httpx
import asyncio

from app.brokers.kis_client import KisClient
from app.brokers.kis_rank_client import KisRankClient, _extract_rows


def test_extract_rows_accepts_output_list():
    rows = _extract_rows({"output": [{"stck_shrn_iscd": "005930"}]})

    assert rows == [{"stck_shrn_iscd": "005930"}]


def test_rank_client_loads_ranked_domestic_snapshots(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200,
                json={"access_token": "sample-access-token", "token_type": "Bearer", "expires_in": 3600},
            )
        if request.url.path == "/uapi/domestic-stock/v1/ranking/fluctuation":
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": [
                        {"stck_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자"},
                        {"stck_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자"},
                    ],
                },
            )
        if request.url.path == "/uapi/domestic-stock/v1/quotations/volume-rank":
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": [
                        {"stck_shrn_iscd": "005930", "hts_kor_isnm": "삼성전자"},
                    ],
                },
            )
        if request.url.path == "/uapi/domestic-stock/v1/quotations/inquire-price":
            assert request.url.params["FID_INPUT_ISCD"] == "005930"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": {
                        "stck_prpr": "322000",
                        "prdy_ctrt": "8.97",
                        "acml_vol": "30124249",
                        "acml_tr_pbmn": "9419668803569",
                        "stck_hgpr": "324000",
                        "stck_lwpr": "300000",
                    },
                },
            )
        return httpx.Response(404)

    kis_client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    rank_client = KisRankClient(kis_client=kis_client, request_interval_seconds=0, rank_count=10)

    snapshots = asyncio.run(rank_client.get_kr_snapshots())

    assert len(snapshots) == 1
    assert snapshots[0].symbol == "005930"
    assert snapshots[0].price == 322000
    assert snapshots[0].volume_ratio == 4.0


def test_rank_client_loads_ranked_us_snapshots(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/tokenP":
            return httpx.Response(
                200,
                json={"access_token": "sample-access-token", "token_type": "Bearer", "expires_in": 3600},
            )
        if request.url.path == "/uapi/overseas-stock/v1/ranking/volume-surge":
            return httpx.Response(200, json={"rt_cd": "0", "output2": [{"symb": "NVDA", "name": "NVIDIA"}]})
        if request.url.path == "/uapi/overseas-stock/v1/ranking/volume-power":
            return httpx.Response(200, json={"rt_cd": "0", "output2": [{"symb": "NVDA", "name": "NVIDIA"}]})
        if request.url.path == "/uapi/overseas-price/v1/quotations/price":
            assert request.url.params["EXCD"] == "NAS"
            assert request.url.params["SYMB"] == "NVDA"
            return httpx.Response(
                200,
                json={
                    "rt_cd": "0",
                    "output": {
                        "last": "208.86",
                        "rate": "4.20",
                        "tvol": "1000000",
                        "tamt": "208860000",
                    },
                },
            )
        return httpx.Response(404)

    kis_client = KisClient(
        app_key="app-key",
        app_secret="app-secret",
        env="real",
        token_cache_path=str(tmp_path / "kis_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    rank_client = KisRankClient(kis_client=kis_client, request_interval_seconds=0, rank_count=10)

    snapshots = asyncio.run(rank_client.get_us_snapshots())

    assert len(snapshots) == 1
    assert snapshots[0].symbol == "NVDA"
    assert snapshots[0].price == 208.86
    assert snapshots[0].volume_ratio == 4.0
