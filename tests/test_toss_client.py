import httpx

from app.brokers.toss_client import TossClient, build_us_snapshot_from_toss


def test_toss_client_maps_us_snapshot(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "token", "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == "/api/v1/prices":
            assert request.url.params["symbols"] == "NVDA"
            return httpx.Response(200, json={"result": [{"symbol": "NVDA", "lastPrice": "150.00", "currency": "USD"}]})
        if request.url.path == "/api/v1/stocks":
            return httpx.Response(
                200,
                json={
                    "result": [
                        {
                            "symbol": "NVDA",
                            "englishName": "NVIDIA",
                            "market": "NASDAQ",
                            "securityType": "FOREIGN_STOCK",
                            "isCommonShare": True,
                            "status": "ACTIVE",
                        }
                    ]
                },
            )
        if request.url.path == "/api/v1/candles":
            assert request.url.params["symbol"] == "NVDA"
            if request.url.params["interval"] == "1m":
                minute_candles = [
                    {
                        "timestamp": f"2026-06-11T09:{idx:02d}:00-04:00",
                        "openPrice": "150",
                        "highPrice": "150",
                        "lowPrice": "150",
                        "closePrice": "150",
                        "volume": "10" if idx < 30 else "100",
                    }
                    for idx in range(40)
                ]
                return httpx.Response(200, json={"result": {"candles": minute_candles}})
            return httpx.Response(
                200,
                json={
                    "result": {
                        "candles": [
                            {
                                "timestamp": "2026-06-10T00:00:00-04:00",
                                "openPrice": "100",
                                "highPrice": "110",
                                "lowPrice": "95",
                                "closePrice": "100",
                                "volume": "1000",
                            },
                            {
                                "timestamp": "2026-06-11T00:00:00-04:00",
                                "openPrice": "140",
                                "highPrice": "151",
                                "lowPrice": "139",
                                "closePrice": "150",
                                "volume": "5000",
                            },
                        ]
                    }
                },
            )
        if request.url.path == "/api/v1/exchange-rate":
            return httpx.Response(200, json={"result": {"rate": "1400", "midRate": "1395"}})
        return httpx.Response(404)

    client = TossClient(
        api_key="api-key",
        secret_key="secret-key",
        base_url="https://example.test",
        token_cache_path=str(tmp_path / "toss_token.json"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    snapshot = client.get_us_snapshot("NVDA")

    assert snapshot.symbol == "NVDA"
    assert snapshot.name == "NVIDIA"
    assert snapshot.price == 150
    assert snapshot.change_pct == 50
    assert snapshot.volume_ratio == 10
    assert snapshot.trading_value_krw == 150 * 5000 * 1400
    assert snapshot.exchange == "NAS"


def test_build_us_snapshot_falls_back_to_open_change_when_previous_close_missing():
    snapshot = build_us_snapshot_from_toss(
        symbol="AAPL",
        price_row={"symbol": "AAPL", "lastPrice": "105"},
        stock_row={"symbol": "AAPL", "englishName": "Apple", "market": "NASDAQ"},
        candles=[
            {
                "timestamp": "2026-06-11T00:00:00-04:00",
                "openPrice": "100",
                "highPrice": "106",
                "lowPrice": "99",
                "closePrice": "105",
                "volume": "1000",
            }
        ],
        usd_krw=1400,
    )

    assert snapshot.change_pct == 5
    assert snapshot.volume_ratio == 1


def test_build_us_snapshot_uses_minute_volume_ratio_when_daily_volume_is_partial():
    minute_candles = [
        {
            "timestamp": f"2026-06-11T09:{idx:02d}:00-04:00",
            "volume": "10" if idx < 30 else "100",
        }
        for idx in range(40)
    ]

    snapshot = build_us_snapshot_from_toss(
        symbol="IONQ",
        price_row={"symbol": "IONQ", "lastPrice": "12"},
        stock_row={"symbol": "IONQ", "englishName": "IonQ", "market": "NYSE"},
        candles=[
            {"timestamp": "2026-06-10T00:00:00-04:00", "closePrice": "10", "volume": "1000000"},
            {"timestamp": "2026-06-11T00:00:00-04:00", "openPrice": "10", "closePrice": "12", "volume": "100"},
        ],
        usd_krw=1400,
        minute_candles=minute_candles,
    )

    assert snapshot.volume_ratio == 10
