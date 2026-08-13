from app.brokers.kis_client import MinuteBar, PriceSnapshot
from app.scanners.momentum import (
    MomentumScanner,
    analyze_minute_momentum,
    parse_exchange_map,
    parse_symbol_list,
)
from app.trading.strategy import StrategyRules


class FakeQuoteClient:
    def __init__(self, snapshots, bars):
        self.snapshots = snapshots
        self.bars = bars
        self.requested_exchanges = {}

    def get_domestic_price(self, symbol: str, name: str | None = None):
        return self.snapshots[symbol]

    def get_overseas_price(self, symbol: str, exchange: str = "NAS", name: str | None = None):
        self.requested_exchanges[symbol] = exchange
        return self.snapshots[symbol]

    def get_domestic_minute_bars(self, symbol: str, limit: int = 30):
        return self.bars[symbol][-limit:]

    def get_overseas_minute_bars(self, symbol: str, exchange: str = "NAS", limit: int = 20):
        self.requested_exchanges[symbol] = exchange
        return self.bars[symbol][-limit:]


def test_parse_symbol_list_cleans_duplicates():
    assert parse_symbol_list(" nvda, hood,\nNVDA ") == ["NVDA", "HOOD"]


def test_parse_exchange_map_normalizes_values():
    assert parse_exchange_map(" ionq:nys, nvda: nas ") == {"IONQ": "NYS", "NVDA": "NAS"}


def test_minute_momentum_uses_completed_bar_volume_and_breakout():
    momentum = analyze_minute_momentum(101.4, _strong_bars())

    assert momentum.relative_volume == 5.0
    assert momentum.one_minute_change_pct > 0.3
    assert momentum.five_minute_change_pct > 0.7
    assert momentum.breakout_pct > 0
    assert 0 <= momentum.vwap_extension_pct < 2.5
    assert momentum.confirmation_bars == 12
    assert momentum.volume_acceleration == 5.0
    assert momentum.pullback_depth_pct == 0.0
    assert momentum.rebreak_pct > 0


def test_minute_momentum_measures_pullback_and_rebreak():
    bars = _strong_bars()
    completed = bars[-2]
    bars[-2] = MinuteBar(
        timestamp=completed.timestamp,
        open=101.0,
        high=101.2,
        low=100.4,
        close=100.8,
        volume=5000,
    )

    momentum = analyze_minute_momentum(101.2, bars)

    assert momentum.pullback_depth_pct > 0
    assert momentum.rebreak_pct > 0
    assert momentum.volume_acceleration == 5.0


def test_minute_momentum_does_not_mix_previous_session_bars():
    previous_day = [
        MinuteBar(f"2026072309{minute:02d}00", 90, 91, 89, 90, 1000)
        for minute in range(10)
    ]
    current_day = _strong_bars()[:5]

    momentum = analyze_minute_momentum(current_day[-1].close, previous_day + current_day)

    assert momentum.confirmation_bars == 5
    assert momentum.relative_volume == 0.0


def test_momentum_scanner_confirms_candidate_with_minute_bars_and_exchange():
    client = FakeQuoteClient(
        {
            "IONQ": PriceSnapshot("IONQ", "IonQ", "US", 101.4, 6.0, 5_000_000_000, "NYS"),
            "SLOW": PriceSnapshot("SLOW", "Slow", "US", 10.0, 1.0, 5_000_000_000, "NAS"),
        },
        {"IONQ": _strong_bars(), "SLOW": _strong_bars()},
    )
    scanner = MomentumScanner(quote_client=client, rules=StrategyRules())

    candidates = scanner.scan_us(["SLOW", "IONQ"], limit=2, exchange_by_symbol={"IONQ": "NYS"})

    assert [candidate.signal.symbol for candidate in candidates] == ["IONQ"]
    assert candidates[0].signal.volume_ratio == 5.0
    assert candidates[0].signal.volume_acceleration == 5.0
    assert candidates[0].signal.rebreak_pct > 0
    assert candidates[0].signal.confirmation_bars == 12
    assert candidates[0].source == "kis_us_minute_confirmed"
    assert client.requested_exchanges["IONQ"] == "NYS"


def test_momentum_scanner_scans_kr_symbols():
    scanner = MomentumScanner(
        quote_client=FakeQuoteClient(
            {
                "005930": PriceSnapshot("005930", "삼성전자", "KR", 101400, 4.0, 2_000_000_000),
            },
            {"005930": _strong_bars(scale=1000)},
        ),
        rules=StrategyRules(entry_min_trading_value_krw=1_000_000_000),
    )

    candidates = scanner.scan_kr(["005930"], limit=1)

    assert candidates[0].signal.market == "KR"
    assert candidates[0].signal.name == "삼성전자"
    assert candidates[0].source == "kis_kr_minute_confirmed"


def _strong_bars(scale: float = 1.0) -> list[MinuteBar]:
    closes = [100.0, 100.1, 100.2, 100.3, 100.4, 100.5, 100.6, 100.7, 100.8, 100.9, 101.3, 101.4]
    volumes = [1000.0] * 10 + [5000.0, 200.0]
    return [
        MinuteBar(
            timestamp=f"2026072409{minute:02d}00",
            open=(close - 0.1) * scale,
            high=(close + 0.1) * scale,
            low=(close - 0.2) * scale,
            close=close * scale,
            volume=volume,
        )
        for minute, (close, volume) in enumerate(zip(closes, volumes))
    ]
