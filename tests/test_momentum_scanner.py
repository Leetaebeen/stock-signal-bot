from app.brokers.kis_client import PriceSnapshot
from app.scanners.momentum import MomentumScanner, TradingValueBaseline, parse_symbol_list


class FakeQuoteClient:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def get_domestic_price(self, symbol: str, name: str | None = None):
        return self.snapshots[symbol]

    def get_overseas_price(self, symbol: str, exchange: str = "NAS", name: str | None = None):
        return self.snapshots[symbol]


def test_parse_symbol_list_cleans_duplicates():
    assert parse_symbol_list(" nvda, hood,\nNVDA ") == ["NVDA", "HOOD"]


def test_trading_value_baseline_calculates_ratio_after_first_observation():
    baseline = TradingValueBaseline()

    assert baseline.volume_ratio("NVDA", 100) == 1.0
    assert baseline.volume_ratio("NVDA", 450) == 4.5


def test_momentum_scanner_returns_sorted_candidates():
    scanner = MomentumScanner(
        quote_client=FakeQuoteClient(
            {
                "AAA": PriceSnapshot("AAA", "AAA", "US", 10, 2.0, 1_000_000_000, "NAS"),
                "BBB": PriceSnapshot("BBB", "BBB", "US", 20, 6.0, 5_000_000_000, "NAS"),
            }
        )
    )

    candidates = scanner.scan_us(["AAA", "BBB"], limit=2)

    assert [candidate.signal.symbol for candidate in candidates] == ["BBB", "AAA"]
    assert candidates[0].signal.volume_ratio == 1.0


def test_momentum_scanner_scans_kr_symbols():
    scanner = MomentumScanner(
        quote_client=FakeQuoteClient(
            {
                "005930": PriceSnapshot("005930", "삼성전자", "KR", 78000, 4.0, 2_000_000_000),
            }
        )
    )

    candidates = scanner.scan_kr(["005930"], limit=1)

    assert candidates[0].signal.market == "KR"
    assert candidates[0].signal.name == "삼성전자"
    assert candidates[0].source == "kis_kr_quote"
