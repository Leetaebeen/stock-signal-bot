import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


FEATURE_NAMES = (
    "change_pct",
    "volume_ratio",
    "log_trading_value_krw",
    "one_minute_change_pct",
    "five_minute_change_pct",
    "breakout_pct",
    "vwap_extension_pct",
    "volume_acceleration",
    "pullback_depth_pct",
    "rebreak_pct",
    "confirmation_bars",
    "score",
)


@dataclass(frozen=True)
class TrainingSample:
    observed_date: str
    symbol: str
    market: str
    features: tuple[float, ...]
    return_30m: float


@dataclass(frozen=True)
class LogisticModel:
    feature_names: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[float, ...]
    threshold: float

    def predict_probability(self, features: tuple[float, ...]) -> float:
        standardized = [
            (value - mean) / scale
            for value, mean, scale in zip(features, self.means, self.scales)
        ]
        score = self.weights[0] + sum(
            weight * value
            for weight, value in zip(self.weights[1:], standardized)
        )
        return _sigmoid(score)

    def as_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["feature_names"] = list(self.feature_names)
        payload["means"] = list(self.means)
        payload["scales"] = list(self.scales)
        payload["weights"] = list(self.weights)
        return payload


@dataclass(frozen=True)
class BacktestReport:
    status: str
    rows: int
    distinct_days: int
    distinct_symbols: int
    train_rows: int = 0
    test_rows: int = 0
    test_days: int = 0
    baseline_precision_pct: float = 0.0
    selected_picks: int = 0
    selected_precision_pct: float = 0.0
    selected_average_return_pct: float = 0.0
    selected_average_net_return_pct: float = 0.0
    validation_folds: int = 0
    profitable_folds: int = 0
    eligible_for_runtime: bool = False
    reason: str = ""


def evaluate_dataset(
    dataset_path: str | Path,
    *,
    model_output_path: str | Path | None = None,
    min_samples: int = 200,
    min_days: int = 20,
    min_symbols: int = 10,
    target_return_pct: float = 0.5,
    round_trip_cost_pct: float = 0.2,
    min_precision_pct: float = 55.0,
    min_test_picks: int = 20,
    probability_threshold: float = 0.6,
    market: str | None = None,
    walk_forward_folds: int = 3,
) -> BacktestReport:
    samples = load_samples(dataset_path)
    normalized_market = market.strip().upper() if market else None
    if normalized_market:
        samples = [item for item in samples if item.market == normalized_market]
    dates = sorted({item.observed_date for item in samples})
    symbols = {item.symbol for item in samples}
    reasons = []
    if len(samples) < min_samples:
        reasons.append(f"samples {len(samples)}/{min_samples}")
    if len(dates) < min_days:
        reasons.append(f"days {len(dates)}/{min_days}")
    if len(symbols) < min_symbols:
        reasons.append(f"symbols {len(symbols)}/{min_symbols}")
    if len(dates) < 2:
        reasons.append("at least 2 dates required")
    if reasons:
        _remove_model(model_output_path)
        return BacktestReport(
            status="COLLECTING",
            rows=len(samples),
            distinct_days=len(dates),
            distinct_symbols=len(symbols),
            reason=", ".join(reasons),
        )

    initial_train_days = min(max(int(len(dates) * 0.6), 1), len(dates) - 1)
    initial_train_date_set = set(dates[:initial_train_days])
    validation_groups = _chunk_dates(
        dates[initial_train_days:],
        max(int(walk_forward_folds), 1),
    )
    selected: list[TrainingSample] = []
    validation: list[TrainingSample] = []
    profitable_folds = 0
    for validation_dates in validation_groups:
        first_validation_date = min(validation_dates)
        train = [item for item in samples if item.observed_date < first_validation_date]
        test = [item for item in samples if item.observed_date in validation_dates]
        model = train_logistic_model(
            train,
            target_return_pct=target_return_pct,
            probability_threshold=probability_threshold,
        )
        fold_selected = [
            item
            for item in test
            if model.predict_probability(item.features) >= model.threshold
        ]
        validation.extend(test)
        selected.extend(fold_selected)
        if fold_selected:
            fold_average = sum(item.return_30m for item in fold_selected) / len(fold_selected)
            if fold_average - round_trip_cost_pct > 0:
                profitable_folds += 1

    positives = sum(item.return_30m >= target_return_pct for item in validation)
    selected_positives = sum(item.return_30m >= target_return_pct for item in selected)
    precision = (selected_positives / len(selected) * 100) if selected else 0.0
    average_return = (
        sum(item.return_30m for item in selected) / len(selected)
        if selected
        else 0.0
    )
    average_net_return = average_return - round_trip_cost_pct if selected else 0.0
    eligible = (
        len(selected) >= min_test_picks
        and precision >= min_precision_pct
        and average_net_return > 0
        and profitable_folds >= math.ceil(len(validation_groups) * (2 / 3))
    )
    report = BacktestReport(
        status="EVALUATED",
        rows=len(samples),
        distinct_days=len(dates),
        distinct_symbols=len(symbols),
        train_rows=sum(item.observed_date in initial_train_date_set for item in samples),
        test_rows=len(validation),
        test_days=sum(len(group) for group in validation_groups),
        baseline_precision_pct=(positives / len(validation) * 100) if validation else 0.0,
        selected_picks=len(selected),
        selected_precision_pct=precision,
        selected_average_return_pct=average_return,
        selected_average_net_return_pct=average_net_return,
        validation_folds=len(validation_groups),
        profitable_folds=profitable_folds,
        eligible_for_runtime=eligible,
        reason=(
            "validation criteria passed"
            if eligible
            else "validation precision, net return, or pick count below threshold"
        ),
    )
    if eligible and model_output_path:
        final_model = train_logistic_model(
            samples,
            target_return_pct=target_return_pct,
            probability_threshold=probability_threshold,
        )
        destination = Path(model_output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(
                {
                    "market": normalized_market,
                    "model": final_model.as_json(),
                    "target_return_pct": target_return_pct,
                    "round_trip_cost_pct": round_trip_cost_pct,
                    "report": asdict(report),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    elif model_output_path:
        _remove_model(model_output_path)
    return report


def _chunk_dates(dates: list[str], requested_chunks: int) -> list[set[str]]:
    if not dates:
        return []
    chunk_count = min(max(requested_chunks, 1), len(dates))
    base_size, remainder = divmod(len(dates), chunk_count)
    chunks = []
    cursor = 0
    for index in range(chunk_count):
        size = base_size + (1 if index < remainder else 0)
        chunks.append(set(dates[cursor : cursor + size]))
        cursor += size
    return chunks


def _remove_model(model_output_path: str | Path | None) -> None:
    if model_output_path:
        Path(model_output_path).unlink(missing_ok=True)


def load_samples(dataset_path: str | Path) -> list[TrainingSample]:
    samples = []
    with Path(dataset_path).open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            try:
                trading_value = max(float(row["trading_value_krw"]), 0.0)
                features = (
                    float(row["change_pct"]),
                    float(row["volume_ratio"]),
                    math.log1p(trading_value),
                    float(row["one_minute_change_pct"]),
                    float(row["five_minute_change_pct"]),
                    float(row["breakout_pct"]),
                    float(row["vwap_extension_pct"]),
                    float(row["volume_acceleration"]),
                    float(row["pullback_depth_pct"]),
                    float(row["rebreak_pct"]),
                    float(row["confirmation_bars"]),
                    float(row["score"]),
                )
                return_30m = float(row["return_30m"])
                if not all(math.isfinite(value) for value in (*features, return_30m)):
                    continue
                samples.append(
                    TrainingSample(
                        observed_date=str(row["observed_at"])[:10],
                        symbol=str(row["symbol"]).strip().upper(),
                        market=str(row["market"]).strip().upper(),
                        features=features,
                        return_30m=return_30m,
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return samples


def train_logistic_model(
    samples: list[TrainingSample],
    *,
    target_return_pct: float,
    probability_threshold: float = 0.6,
    epochs: int = 600,
    learning_rate: float = 0.05,
    l2_penalty: float = 0.01,
) -> LogisticModel:
    if not samples:
        raise ValueError("training samples are required")
    columns = list(zip(*(item.features for item in samples)))
    means = tuple(sum(column) / len(column) for column in columns)
    scales = tuple(
        max(
            math.sqrt(sum((value - mean) ** 2 for value in column) / len(column)),
            1e-9,
        )
        for column, mean in zip(columns, means)
    )
    matrix = [
        tuple(
            (value - mean) / scale
            for value, mean, scale in zip(item.features, means, scales)
        )
        for item in samples
    ]
    labels = [1.0 if item.return_30m >= target_return_pct else 0.0 for item in samples]
    weights = [0.0] * (len(FEATURE_NAMES) + 1)
    count = float(len(samples))
    for _ in range(max(epochs, 1)):
        gradients = [0.0] * len(weights)
        for features, label in zip(matrix, labels):
            probability = _sigmoid(
                weights[0]
                + sum(weight * value for weight, value in zip(weights[1:], features))
            )
            error = probability - label
            gradients[0] += error
            for index, value in enumerate(features, start=1):
                gradients[index] += error * value
        weights[0] -= learning_rate * gradients[0] / count
        for index in range(1, len(weights)):
            regularized = (gradients[index] / count) + (l2_penalty * weights[index])
            weights[index] -= learning_rate * regularized
    return LogisticModel(
        feature_names=FEATURE_NAMES,
        means=means,
        scales=scales,
        weights=tuple(weights),
        threshold=probability_threshold,
    )


def _sigmoid(value: float) -> float:
    clipped = max(min(value, 35.0), -35.0)
    return 1.0 / (1.0 + math.exp(-clipped))
