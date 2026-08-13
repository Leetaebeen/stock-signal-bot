import argparse

from app.config import get_settings
from app.learning.feature_report import generate_feature_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/training_signals.csv")
    parser.add_argument("--output", default="data/early_surge_report.json")
    args = parser.parse_args()
    settings = get_settings()
    report = generate_feature_report(
        args.dataset,
        args.output,
        min_bucket_samples=settings.feature_report_min_bucket_samples,
        min_distinct_days=settings.feature_report_min_distinct_days,
        min_distinct_symbols=settings.feature_report_min_distinct_symbols,
        target_return_pct=settings.model_target_return_pct,
        round_trip_cost_pct=settings.model_round_trip_cost_pct,
    )
    print(f"source_rows={report['source_rows']}")
    for market in ("KR", "US"):
        overall = report["markets"][market]["overall"]
        matched = report["markets"][market]["dimensions"]["combined_pattern"]["matched"]
        print(
            f"{market} rows={overall['samples']} matched={matched['samples']} "
            f"matched_net_30m={matched['average_net_return_30m_pct']:+.4f}% "
            f"ready_for_review={str(matched['ready_for_review']).lower()}"
        )
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
