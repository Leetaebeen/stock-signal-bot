from datetime import datetime, timedelta, timezone

from app.brokers.toss_rank_client import _detect_price_spikes, _is_supported_us_stock
from app.brokers.toss_rank_client import TossRankClient


class FakeTossClient:
    def __init__(self):
        self.calls = []

    def get_prices(self, symbols):
        self.calls.append(list(symbols))
        return {symbol: {"symbol": symbol, "lastPrice": "10"} for symbol in symbols}


def test_toss_rank_client_accepts_active_us_common_stock():
    assert _is_supported_us_stock(
        {
            "market": "NASDAQ",
            "securityType": "FOREIGN_STOCK",
            "isCommonShare": True,
            "status": "ACTIVE",
        }
    )


def test_toss_rank_client_rejects_etf_and_delisted_stock():
    assert not _is_supported_us_stock(
        {
            "market": "NASDAQ",
            "securityType": "FOREIGN_ETF",
            "isCommonShare": True,
            "status": "ACTIVE",
        }
    )


def test_toss_rank_client_rotates_symbol_batches(tmp_path):
    client = TossRankClient(
        toss_client=None,
        request_interval_seconds=0,
        rank_count=2,
        scan_cursor_path=str(tmp_path / "cursor.txt"),
    )

    assert client._next_symbol_batch(["A", "B", "C", "D", "E"]) == ["A", "B"]
    assert client._next_symbol_batch(["A", "B", "C", "D", "E"]) == ["C", "D"]
    assert client._next_symbol_batch(["A", "B", "C", "D", "E"]) == ["E", "A"]
    assert not _is_supported_us_stock(
        {
            "market": "NYSE",
            "securityType": "FOREIGN_STOCK",
            "isCommonShare": True,
            "status": "DELISTED",
        }
    )


def test_detect_price_spikes_uses_1m_5m_and_20m_windows():
    now = datetime(2026, 6, 12, 10, 0, tzinfo=timezone.utc)
    cache = {
        "FAST": [
            {"ts": (now - timedelta(minutes=2)).timestamp(), "price": 10.0},
        ],
        "SLOW": [
            {"ts": (now - timedelta(minutes=6)).timestamp(), "price": 10.0},
        ],
        "BASE": [
            {"ts": (now - timedelta(minutes=21)).timestamp(), "price": 10.0},
        ],
        "FLAT": [
            {"ts": (now - timedelta(minutes=21)).timestamp(), "price": 10.0},
        ],
    }
    prices = {
        "FAST": {"lastPrice": "10.4"},
        "SLOW": {"lastPrice": "10.9"},
        "BASE": {"lastPrice": "11.6"},
        "FLAT": {"lastPrice": "10.1"},
    }

    spikes = _detect_price_spikes(
        prices,
        cache,
        now,
        thresholds={"1m": 3.0, "5m": 8.0, "20m": 15.0},
    )

    assert [item["symbol"] for item in spikes] == ["FAST", "SLOW", "BASE"]


def test_sweep_prices_respects_200_symbol_batches(tmp_path):
    fake = FakeTossClient()
    client = TossRankClient(
        toss_client=fake,
        request_interval_seconds=0,
        rank_count=40,
        spike_cache_path=str(tmp_path / "cache.json"),
    )
    symbols = [f"S{i}" for i in range(401)]

    prices = client._sweep_prices(symbols)

    assert len(prices) == 401
    assert [len(call) for call in fake.calls] == [200, 200, 1]
