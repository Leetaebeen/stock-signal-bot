import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

from app.learning.evaluator import FEATURE_NAMES, LogisticModel
from app.trading.strategy import MarketSignal


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelGateDecision:
    allowed: bool
    probability: float | None
    reason: str


class RuntimeModelGate:
    def __init__(self, *, enabled: bool, model_output_path: str | Path) -> None:
        self.enabled = enabled
        self.model_output_path = Path(model_output_path)
        self._cache: dict[str, tuple[int, LogisticModel | None]] = {}

    def evaluate(self, signal: MarketSignal, *, score: float) -> ModelGateDecision:
        if not self.enabled:
            return ModelGateDecision(True, None, "model filter disabled")
        model = self._load(signal.market)
        if model is None:
            return ModelGateDecision(True, None, "validated market model unavailable")
        probability = model.predict_probability(_signal_features(signal, score))
        if probability < model.threshold:
            return ModelGateDecision(
                False,
                probability,
                f"model probability {probability:.3f} below {model.threshold:.3f}",
            )
        return ModelGateDecision(
            True,
            probability,
            f"model probability {probability:.3f} passed {model.threshold:.3f}",
        )

    def _load(self, market: str) -> LogisticModel | None:
        normalized_market = market.strip().upper()
        path = market_model_path(self.model_output_path, normalized_market)
        if not path.exists():
            self._cache.pop(normalized_market, None)
            return None
        modified = path.stat().st_mtime_ns
        cached = self._cache.get(normalized_market)
        if cached and cached[0] == modified:
            return cached[1]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if str(payload.get("market") or "").upper() != normalized_market:
                raise ValueError("model market does not match file name")
            raw = payload["model"]
            feature_names = tuple(str(item) for item in raw["feature_names"])
            if feature_names != FEATURE_NAMES:
                raise ValueError("model feature schema does not match runtime")
            model = LogisticModel(
                feature_names=feature_names,
                means=tuple(float(item) for item in raw["means"]),
                scales=tuple(float(item) for item in raw["scales"]),
                weights=tuple(float(item) for item in raw["weights"]),
                threshold=float(raw["threshold"]),
            )
            if not (
                len(model.means) == len(FEATURE_NAMES)
                and len(model.scales) == len(FEATURE_NAMES)
                and len(model.weights) == len(FEATURE_NAMES) + 1
            ):
                raise ValueError("model dimensions do not match runtime")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("runtime model ignored market=%s path=%s reason=%s", normalized_market, path, exc)
            model = None
        self._cache[normalized_market] = (modified, model)
        return model


def market_model_path(base_path: str | Path, market: str) -> Path:
    path = Path(base_path)
    suffix = path.suffix or ".json"
    return path.with_name(f"{path.stem}_{market.strip().lower()}{suffix}")


def _signal_features(signal: MarketSignal, score: float) -> tuple[float, ...]:
    return (
        float(signal.change_pct),
        float(signal.volume_ratio),
        math.log1p(max(float(signal.trading_value_krw), 0.0)),
        float(signal.one_minute_change_pct),
        float(signal.five_minute_change_pct),
        float(signal.breakout_pct),
        float(signal.vwap_extension_pct),
        float(signal.volume_acceleration),
        float(signal.pullback_depth_pct),
        float(signal.rebreak_pct),
        float(signal.confirmation_bars),
        float(score),
    )
