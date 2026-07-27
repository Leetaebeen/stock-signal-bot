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
    "confirmation_bars",
    "score",
    "return_5m",
    "return_15m",
    "return_30m",
]


def test_evaluator_blocks_single_day_dataset(tmp_path):
    dataset = tmp_path / "single_day.csv"
    _write_dataset(dataset, days=1, rows_per_day=20)

    report = evaluate_dataset(
        dataset,
        model_output_path=tmp_path / "model.json",
        min_samples=10,
        min_days=5,
        min_symbols=5,
    )

    assert report.status == "COLLECTING"
    assert report.distinct_days == 1
    assert "days 1/5" in report.reason
    assert not (tmp_path / "model.json").exists()


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
    assert report.train_rows == 192
    assert report.test_rows == 48
    assert report.test_days == 4
    assert report.selected_precision_pct == 100
    assert report.eligible_for_runtime
    assert model_path.exists()
    assert len(load_samples(dataset)[0].features) == len(FEATURE_NAMES)


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
                        "confirmation_bars": 12,
                        "score": 85 if positive else 60,
                        "return_5m": 0.4 if positive else -0.2,
                        "return_15m": 0.8 if positive else -0.4,
                        "return_30m": 1.2 if positive else -0.6,
                    }
                )
