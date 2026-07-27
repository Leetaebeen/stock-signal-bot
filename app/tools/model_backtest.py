import argparse

from app.config import get_settings
from app.learning.evaluator import evaluate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/training_signals.csv")
    parser.add_argument("--model-output", default="data/momentum_model.json")
    args = parser.parse_args()
    settings = get_settings()
    report = evaluate_dataset(
        args.dataset,
        model_output_path=args.model_output,
        min_samples=settings.learning_min_labeled_samples,
        min_days=settings.learning_min_distinct_days,
        min_symbols=settings.learning_min_distinct_symbols,
        target_return_pct=settings.model_target_return_pct,
        round_trip_cost_pct=settings.model_round_trip_cost_pct,
        min_precision_pct=settings.model_min_precision_pct,
        min_test_picks=settings.model_min_test_picks,
    )
    print(f"status={report.status}")
    print(
        f"rows={report.rows} distinct_days={report.distinct_days} "
        f"distinct_symbols={report.distinct_symbols}"
    )
    if report.status == "EVALUATED":
        print(
            f"train_rows={report.train_rows} test_rows={report.test_rows} "
            f"test_days={report.test_days}"
        )
        print(
            f"baseline_precision={report.baseline_precision_pct:.2f}% "
            f"selected_picks={report.selected_picks} "
            f"selected_precision={report.selected_precision_pct:.2f}%"
        )
        print(
            f"average_return={report.selected_average_return_pct:+.3f}% "
            f"average_net_return={report.selected_average_net_return_pct:+.3f}%"
        )
    print(f"eligible_for_runtime={str(report.eligible_for_runtime).lower()}")
    print(f"reason={report.reason}")


if __name__ == "__main__":
    main()
