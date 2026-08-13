import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import fmean
from typing import Callable


@dataclass(frozen=True)
class FeatureObservation:
    symbol: str
    market: str
    observed_date: str
    volume_acceleration: float
    breakout_pct: float
    pullback_depth_pct: float
    rebreak_pct: float
    return_5m: float
    return_15m: float
    return_30m: float


BucketRule = tuple[str, Callable[[FeatureObservation], bool]]


FEATURE_BUCKETS: dict[str, tuple[BucketRule, ...]] = {
    "volume_acceleration": (
        ("below_2x", lambda row: row.volume_acceleration < 2),
        ("2x_to_4x", lambda row: 2 <= row.volume_acceleration < 4),
        ("4x_to_8x", lambda row: 4 <= row.volume_acceleration < 8),
        ("8x_or_more", lambda row: row.volume_acceleration >= 8),
    ),
    "breakout_pct": (
        ("below_zero", lambda row: row.breakout_pct < 0),
        ("zero_to_0_3", lambda row: 0 <= row.breakout_pct < 0.3),
        ("0_3_to_1", lambda row: 0.3 <= row.breakout_pct < 1),
        ("1_or_more", lambda row: row.breakout_pct >= 1),
    ),
    "pullback_depth_pct": (
        ("no_pullback", lambda row: row.pullback_depth_pct <= 0),
        ("zero_to_0_5", lambda row: 0 < row.pullback_depth_pct < 0.5),
        ("0_5_to_1_5", lambda row: 0.5 <= row.pullback_depth_pct < 1.5),
        ("1_5_to_3", lambda row: 1.5 <= row.pullback_depth_pct < 3),
        ("3_or_more", lambda row: row.pullback_depth_pct >= 3),
    ),
    "rebreak_pct": (
        ("below_zero", lambda row: row.rebreak_pct < 0),
        ("zero_to_0_3", lambda row: 0 <= row.rebreak_pct < 0.3),
        ("0_3_to_1", lambda row: 0.3 <= row.rebreak_pct < 1),
        ("1_or_more", lambda row: row.rebreak_pct >= 1),
    ),
    "combined_pattern": (
        ("matched", lambda row: _matches_early_surge_pattern(row)),
        ("not_matched", lambda row: not _matches_early_surge_pattern(row)),
    ),
}


def generate_feature_report(
    dataset_path: str | Path,
    output_path: str | Path,
    *,
    min_bucket_samples: int = 30,
    min_distinct_days: int = 5,
    min_distinct_symbols: int = 5,
    target_return_pct: float = 0.5,
    round_trip_cost_pct: float = 0.2,
    generated_at: datetime | None = None,
) -> dict:
    observations = load_feature_observations(dataset_path)
    requirements = {
        "min_bucket_samples": max(int(min_bucket_samples), 1),
        "min_distinct_days": max(int(min_distinct_days), 1),
        "min_distinct_symbols": max(int(min_distinct_symbols), 1),
        "target_return_pct": float(target_return_pct),
        "round_trip_cost_pct": float(round_trip_cost_pct),
    }
    markets = {}
    for market in ("KR", "US"):
        market_rows = [row for row in observations if row.market == market]
        dimensions = {}
        for feature_name, bucket_rules in FEATURE_BUCKETS.items():
            dimensions[feature_name] = {
                bucket_name: _summarize(
                    [row for row in market_rows if predicate(row)],
                    requirements,
                )
                for bucket_name, predicate in bucket_rules
            }
        markets[market] = {
            "overall": _summarize(market_rows, requirements),
            "dimensions": dimensions,
        }

    timestamp = generated_at or datetime.now(timezone.utc)
    report = {
        "version": 1,
        "generated_at": timestamp.astimezone(timezone.utc).isoformat(),
        "source_rows": len(observations),
        "requirements": requirements,
        "pattern_definition": {
            "volume_acceleration_min": 2.0,
            "breakout_pct_min": 0.0,
            "pullback_depth_pct_min": 0.2,
            "pullback_depth_pct_max": 2.0,
            "rebreak_pct_min": 0.0,
            "rebreak_pct_max": 1.5,
        },
        "markets": markets,
    }
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def load_feature_observations(dataset_path: str | Path) -> list[FeatureObservation]:
    observations = []
    path = Path(dataset_path)
    if not path.exists():
        return observations
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            try:
                observation = FeatureObservation(
                    symbol=str(row["symbol"]).strip().upper(),
                    market=str(row["market"]).strip().upper(),
                    observed_date=str(row["observed_at"])[:10],
                    volume_acceleration=float(row["volume_acceleration"]),
                    breakout_pct=float(row["breakout_pct"]),
                    pullback_depth_pct=float(row["pullback_depth_pct"]),
                    rebreak_pct=float(row["rebreak_pct"]),
                    return_5m=float(row["return_5m"]),
                    return_15m=float(row["return_15m"]),
                    return_30m=float(row["return_30m"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            numeric_values = (
                observation.volume_acceleration,
                observation.breakout_pct,
                observation.pullback_depth_pct,
                observation.rebreak_pct,
                observation.return_5m,
                observation.return_15m,
                observation.return_30m,
            )
            if (
                observation.market not in {"KR", "US"}
                or not observation.symbol
                or not all(math.isfinite(value) for value in numeric_values)
            ):
                continue
            observations.append(observation)
    return observations


def _matches_early_surge_pattern(row: FeatureObservation) -> bool:
    return (
        row.volume_acceleration >= 2
        and row.breakout_pct >= 0
        and 0.2 <= row.pullback_depth_pct <= 2.0
        and 0 <= row.rebreak_pct <= 1.5
    )


def _summarize(rows: list[FeatureObservation], requirements: dict) -> dict:
    samples = len(rows)
    distinct_days = len({row.observed_date for row in rows})
    distinct_symbols = len({row.symbol for row in rows})
    if samples:
        average_return_5m = fmean(row.return_5m for row in rows)
        average_return_15m = fmean(row.return_15m for row in rows)
        average_return_30m = fmean(row.return_30m for row in rows)
        positive_rate = sum(row.return_30m > 0 for row in rows) / samples * 100
        target_hit_rate = (
            sum(row.return_30m >= requirements["target_return_pct"] for row in rows)
            / samples
            * 100
        )
    else:
        average_return_5m = 0.0
        average_return_15m = 0.0
        average_return_30m = 0.0
        positive_rate = 0.0
        target_hit_rate = 0.0
    ready_for_review = (
        samples >= requirements["min_bucket_samples"]
        and distinct_days >= requirements["min_distinct_days"]
        and distinct_symbols >= requirements["min_distinct_symbols"]
    )
    return {
        "samples": samples,
        "distinct_days": distinct_days,
        "distinct_symbols": distinct_symbols,
        "average_return_5m_pct": round(average_return_5m, 4),
        "average_return_15m_pct": round(average_return_15m, 4),
        "average_return_30m_pct": round(average_return_30m, 4),
        "average_net_return_30m_pct": round(
            average_return_30m - requirements["round_trip_cost_pct"] if samples else 0.0,
            4,
        ),
        "positive_rate_30m_pct": round(positive_rate, 2),
        "target_hit_rate_30m_pct": round(target_hit_rate, 2),
        "ready_for_review": ready_for_review,
    }
