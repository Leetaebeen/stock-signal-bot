from dataclasses import dataclass
from datetime import date, datetime
import logging

from app.learning.evaluator import BacktestReport, evaluate_dataset
from app.learning.feature_report import generate_feature_report
from app.learning.runtime_model import market_model_path
from app.trading.journal import TradeJournal
from app.trading.strategy import KST


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LearningRun:
    exported_rows: int
    reports: dict[str, BacktestReport]
    feature_report: dict

    @property
    def report(self) -> BacktestReport:
        return self.reports.get("US") or next(iter(self.reports.values()))


class LearningPipeline:
    def __init__(self, settings, journal: TradeJournal) -> None:
        self.settings = settings
        self.journal = journal
        self._last_run_date: date | None = None

    def maybe_run(self, now: datetime | None = None) -> LearningRun | None:
        current = (now or datetime.now(KST)).astimezone(KST)
        if not getattr(self.settings, "model_auto_evaluate_enabled", True):
            return None
        evaluation_hour = min(
            max(int(getattr(self.settings, "model_evaluation_hour_kst", 17)), 0),
            23,
        )
        if current.hour < evaluation_hour or self._last_run_date == current.date():
            return None

        dataset_path = getattr(
            self.settings,
            "model_training_dataset_path",
            "data/training_signals.csv",
        )
        model_path = getattr(
            self.settings,
            "model_output_path",
            "data/momentum_model.json",
        )
        exported_rows = self.journal.export_training_dataset(dataset_path)
        feature_report = generate_feature_report(
            dataset_path,
            getattr(
                self.settings,
                "feature_report_output_path",
                "data/early_surge_report.json",
            ),
            min_bucket_samples=getattr(
                self.settings,
                "feature_report_min_bucket_samples",
                30,
            ),
            min_distinct_days=getattr(
                self.settings,
                "feature_report_min_distinct_days",
                5,
            ),
            min_distinct_symbols=getattr(
                self.settings,
                "feature_report_min_distinct_symbols",
                5,
            ),
            target_return_pct=getattr(self.settings, "model_target_return_pct", 0.5),
            round_trip_cost_pct=getattr(
                self.settings,
                "model_round_trip_cost_pct",
                0.2,
            ),
            generated_at=current,
        )
        for market in ("KR", "US"):
            matched = feature_report["markets"][market]["dimensions"][
                "combined_pattern"
            ]["matched"]
            logger.info(
                "early surge report market=%s rows=%s matched=%s net_30m=%+.4f%% "
                "ready_for_review=%s",
                market,
                feature_report["markets"][market]["overall"]["samples"],
                matched["samples"],
                matched["average_net_return_30m_pct"],
                matched["ready_for_review"],
            )
        reports = {}
        for market in ("KR", "US"):
            report = evaluate_dataset(
                dataset_path,
                model_output_path=market_model_path(model_path, market),
                min_samples=getattr(self.settings, "learning_min_labeled_samples", 200),
                min_days=getattr(self.settings, "learning_min_distinct_days", 20),
                min_symbols=getattr(self.settings, "learning_min_distinct_symbols", 10),
                target_return_pct=getattr(self.settings, "model_target_return_pct", 0.5),
                round_trip_cost_pct=getattr(
                    self.settings,
                    "model_round_trip_cost_pct",
                    0.2,
                ),
                min_precision_pct=getattr(
                    self.settings,
                    "model_min_precision_pct",
                    55.0,
                ),
                min_test_picks=getattr(self.settings, "model_min_test_picks", 20),
                market=market,
                walk_forward_folds=getattr(self.settings, "model_walk_forward_folds", 3),
            )
            reports[market] = report
            logger.info(
                "learning evaluation market=%s status=%s rows=%s days=%s symbols=%s "
                "folds=%s profitable_folds=%s eligible=%s reason=%s",
                market,
                report.status,
                report.rows,
                report.distinct_days,
                report.distinct_symbols,
                report.validation_folds,
                report.profitable_folds,
                report.eligible_for_runtime,
                report.reason,
            )
        self._last_run_date = current.date()
        return LearningRun(exported_rows, reports, feature_report)
