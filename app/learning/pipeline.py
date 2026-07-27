from dataclasses import dataclass
from datetime import date, datetime
import logging

from app.learning.evaluator import BacktestReport, evaluate_dataset
from app.trading.journal import TradeJournal
from app.trading.strategy import KST


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LearningRun:
    exported_rows: int
    report: BacktestReport


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
        report = evaluate_dataset(
            dataset_path,
            model_output_path=model_path,
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
        )
        self._last_run_date = current.date()
        logger.info(
            "learning evaluation status=%s rows=%s days=%s symbols=%s eligible=%s reason=%s",
            report.status,
            report.rows,
            report.distinct_days,
            report.distinct_symbols,
            report.eligible_for_runtime,
            report.reason,
        )
        return LearningRun(exported_rows, report)
