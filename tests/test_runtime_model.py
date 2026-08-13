import json

from app.learning.evaluator import FEATURE_NAMES
from app.learning.runtime_model import RuntimeModelGate, market_model_path
from app.trading.strategy import MarketSignal


def test_runtime_model_gate_allows_when_validated_model_is_missing(tmp_path):
    gate = RuntimeModelGate(enabled=True, model_output_path=tmp_path / "model.json")

    decision = gate.evaluate(_signal(), score=80)

    assert decision.allowed
    assert decision.probability is None


def test_runtime_model_gate_blocks_probability_below_threshold(tmp_path):
    base_path = tmp_path / "model.json"
    model_path = market_model_path(base_path, "US")
    model_path.write_text(
        json.dumps(
            {
                "market": "US",
                "model": {
                    "feature_names": list(FEATURE_NAMES),
                    "means": [0.0] * len(FEATURE_NAMES),
                    "scales": [1.0] * len(FEATURE_NAMES),
                    "weights": [-10.0] + ([0.0] * len(FEATURE_NAMES)),
                    "threshold": 0.6,
                },
            }
        ),
        encoding="utf-8",
    )
    gate = RuntimeModelGate(enabled=True, model_output_path=base_path)

    decision = gate.evaluate(_signal(), score=80)

    assert not decision.allowed
    assert decision.probability is not None
    assert decision.probability < 0.6


def test_market_model_path_is_separate_per_market(tmp_path):
    base = tmp_path / "momentum_model.json"

    assert market_model_path(base, "KR").name == "momentum_model_kr.json"
    assert market_model_path(base, "US").name == "momentum_model_us.json"


def _signal() -> MarketSignal:
    return MarketSignal(
        symbol="NVDA",
        name="NVIDIA",
        market="US",
        price=100,
        change_pct=6,
        volume_ratio=5,
        trading_value_krw=5_000_000_000,
        one_minute_change_pct=0.5,
        five_minute_change_pct=1.5,
        breakout_pct=0.4,
        vwap_extension_pct=0.8,
        volume_acceleration=4.5,
        pullback_depth_pct=0.6,
        rebreak_pct=0.3,
        confirmation_bars=12,
    )
