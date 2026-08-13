import csv
from datetime import date, timedelta

from app.learning.evaluator import FEATURE_NAMES, evaluate_dataset, load_samples


FIELDS = [
    "symbol",
    "market",
    "exchange",
    "observed_at",
    "price",
    "change_pct",
    "volume_ratio",
    "trading_value_krw",
    "one_minute_change_pct",
    "five_minute_change_pct",
    "breakout_pct",
    "vwap_extension_pct",
    "volume_acceleration",
    "pullback_depth_pct",
    "rebreak_pct",
    "confirmation_bars",
    "score",
    "return_5m",
    "return_15m",
    "return_30m",
]


def test_evaluator_blocks_single_day_dataset(tmp_path):
    dataset = tmp_path / "single_day.csv"
    model_path = tmp_path / "model.json"
    _write_dataset(dataset, days=1, rows_per_day=20)
    model_path.write_text("stale", encoding="utf-8")

    report = evaluate_dataset(
        dataset,
        model_output_path=model_path,
        min_samples=10,
        min_days=5,
        min_symbols=5,
    )

    assert report.status == "COLLECTING"
    assert report.distinct_days == 1
    assert "days 1/5" in report.reason
    assert not model_path.exists()


def test_evaluator_uses_date_split_and_saves_only_validated_model(tmp_path):
    dataset = tmp_path / "training.csv"
    model_path = tmp_path / "model.json"
    _write_dataset(dataset, days=20, rows_per_day=12)

    report = evaluate_dataset(
        dataset,
        model_output_path=model_path,
        min_samples=100,
        min_days=10,
        min_symbols=5,
        min_test_picks=10,
        min_precision_pct=80,
    )

    assert report.status == "EVALUATED"
    assert report.train_rows == 144
    assert report.test_rows == 96
    assert report.test_days == 8
    assert report.validation_folds == 3
    assert report.profitable_folds == 3
    assert report.selected_precision_pct == 100
    assert report.eligible_for_runtime
    assert model_path.exists()
    assert len(load_samples(dataset)[0].features) == len(FEATURE_NAMES)


def test_evaluator_filters_samples_by_market(tmp_path):
    dataset = tmp_path / "training.csv"
    _write_dataset(dataset, days=5, rows_per_day=4)

    report = evaluate_dataset(
        dataset,
        min_samples=1,
        min_days=2,
        min_symbols=1,
        market="KR",
    )

    assert report.status == "COLLECTING"
    assert report.rows == 0
    assert report.distinct_days == 0


def _write_dataset(path, *, days: int, rows_per_day: int) -> None:
    start = date(2026, 1, 2)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        for day_index in range(days):
            observed_date = start + timedelta(days=day_index)
            for row_index in range(rows_per_day):
                positive = row_index % 2 == 0
                writer.writerow(
                    {
                        "symbol": f"T{row_index:02d}",
                        "market": "US",
                        "exchange": "NAS",
                        "observed_at": f"{observed_date.isoformat()}T22:30:00+09:00",
                        "price": 100,
                        "change_pct": 8 if positive else 3,
                        "volume_ratio": 8 if positive else 4,
                        "trading_value_krw": 10_000_000_000,
                        "one_minute_change_pct": 1 if positive else -1,
                        "five_minute_change_pct": 2 if positive else -1,
                        "breakout_pct": 1 if positive else -0.5,
                        "vwap_extension_pct": 0.5 if positive else 2,
                        "volume_acceleration": 6 if positive else 1.2,
                        "pullback_depth_pct": 0.8 if positive else 3,
                        "rebreak_pct": 0.7 if positive else -0.4,
                        "confirmation_bars": 12,
                        "score": 85 if positive else 60,
                        "return_5m": 0.4 if positive else -0.2,
                        "return_15m": 0.8 if positive else -0.4,
                        "return_30m": 1.2 if positive else -0.6,
                    }
                )
