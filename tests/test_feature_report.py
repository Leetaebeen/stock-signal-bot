import csv
from datetime import datetime, timezone
import json

from app.learning.feature_report import generate_feature_report, load_feature_observations


FIELDS = [
    "symbol",
    "market",
    "observed_at",
    "volume_acceleration",
    "breakout_pct",
    "pullback_depth_pct",
    "rebreak_pct",
    "return_5m",
    "return_15m",
    "return_30m",
]


def test_feature_report_summarizes_early_surge_pattern(tmp_path):
    dataset = tmp_path / "training.csv"
    output = tmp_path / "report.json"
    _write_rows(
        dataset,
        [
            _row("AAA", "US", "2026-08-01", 4.0, 0.4, 0.5, 0.4, 1.0),
            _row("BBB", "US", "2026-08-02", 6.0, 0.2, 1.0, 0.6, 2.0),
            _row("CCC", "US", "2026-08-02", 1.2, -0.2, 3.5, -0.4, -1.0),
            _row("005930", "KR", "2026-08-01", 3.0, 0.1, 0.7, 0.2, 0.8),
        ],
    )

    report = generate_feature_report(
        dataset,
        output,
        min_bucket_samples=2,
        min_distinct_days=2,
        min_distinct_symbols=2,
        target_return_pct=0.5,
        round_trip_cost_pct=0.2,
        generated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    matched = report["markets"]["US"]["dimensions"]["combined_pattern"]["matched"]
    assert report["source_rows"] == 4
    assert matched["samples"] == 2
    assert matched["average_return_30m_pct"] == 1.5
    assert matched["average_net_return_30m_pct"] == 1.3
    assert matched["target_hit_rate_30m_pct"] == 100
    assert matched["ready_for_review"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["version"] == 1


def test_feature_report_skips_invalid_rows_and_handles_missing_file(tmp_path):
    dataset = tmp_path / "training.csv"
    _write_rows(
        dataset,
        [
            _row("AAA", "US", "2026-08-01", 4.0, 0.4, 0.5, 0.4, 1.0),
            _row("BAD", "OTHER", "2026-08-01", 4.0, 0.4, 0.5, 0.4, 1.0),
        ],
    )

    assert len(load_feature_observations(dataset)) == 1
    assert load_feature_observations(tmp_path / "missing.csv") == []


def _row(symbol, market, observed_date, acceleration, breakout, pullback, rebreak, return_30m):
    return {
        "symbol": symbol,
        "market": market,
        "observed_at": f"{observed_date}T22:30:00+09:00",
        "volume_acceleration": acceleration,
        "breakout_pct": breakout,
        "pullback_depth_pct": pullback,
        "rebreak_pct": rebreak,
        "return_5m": return_30m / 3,
        "return_15m": return_30m / 2,
        "return_30m": return_30m,
    }


def _write_rows(path, rows):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
