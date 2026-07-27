from app.brokers.kis_client import RankedSymbol
from app.scanners.universe import DynamicUniverseProvider, parse_exchanges


class FakeRankingClient:
    def __init__(self) -> None:
        self.kr_calls = 0
        self.us_calls = 0

    def get_domestic_ranked_symbols(self, limit=20):
        self.kr_calls += 1
        return [
            RankedSymbol("005930", "Samsung", "KR", "KRX"),
            RankedSymbol("000660", "SK Hynix", "KR", "KRX"),
        ][:limit]

    def get_overseas_ranked_symbols(self, exchange="NAS", limit=10):
        self.us_calls += 1
        return [RankedSymbol(f"{exchange}1", exchange, "US", exchange)][:limit]


def test_dynamic_universe_uses_rankings_and_cache():
    client = FakeRankingClient()
    provider = DynamicUniverseProvider(
        client,
        refresh_seconds=300,
        us_exchanges=("NAS", "NYS"),
    )

    first = provider.select_kr(["035420"])
    second = provider.select_kr(["035420"])
    us = provider.select_us(["NVDA"], {"NVDA": "NAS"})

    assert first.symbols == ["005930", "000660"]
    assert first.source == "kis_rank"
    assert second == first
    assert client.kr_calls == 1
    assert us.symbols == ["NAS1", "NYS1"]
    assert us.exchange_by_symbol == {"NAS1": "NAS", "NYS1": "NYS"}
    assert us.name_by_symbol == {"NAS1": "NAS", "NYS1": "NYS"}


def test_dynamic_universe_falls_back_when_ranking_fails():
    class BrokenClient:
        def get_domestic_ranked_symbols(self, limit=20):
            raise RuntimeError("unsupported")

    provider = DynamicUniverseProvider(BrokenClient())
    result = provider.select_kr(["005930", "005930", "000660"])

    assert result.symbols == ["005930", "000660"]
    assert result.source == "configured_fallback"


def test_parse_exchanges_dedupes_values():
    assert parse_exchanges("NAS, NYS,NAS,AMS") == ("NAS", "NYS", "AMS")
