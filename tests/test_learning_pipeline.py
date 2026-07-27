from datetime import datetime

from app.learning.pipeline import LearningPipeline
from app.trading.journal import TradeJournal
from app.trading.strategy import KST


class PipelineSettings:
    model_auto_evaluate_enabled = True
    model_evaluation_hour_kst = 17
    learning_min_labeled_samples = 200
    learning_min_distinct_days = 20
    learning_min_distinct_symbols = 10
    model_target_return_pct = 0.5
    model_round_trip_cost_pct = 0.2
    model_min_precision_pct = 55
    model_min_test_picks = 20


def test_learning_pipeline_runs_once_after_configured_hour(tmp_path):
    settings = PipelineSettings()
    settings.model_training_dataset_path = str(tmp_path / "training.csv")
    settings.model_output_path = str(tmp_path / "model.json")
    pipeline = LearningPipeline(settings, TradeJournal(tmp_path / "trades.db"))

    before = pipeline.maybe_run(datetime(2026, 7, 27, 16, 59, tzinfo=KST))
    first = pipeline.maybe_run(datetime(2026, 7, 27, 17, 0, tzinfo=KST))
    second = pipeline.maybe_run(datetime(2026, 7, 27, 18, 0, tzinfo=KST))

    assert before is None
    assert first is not None
    assert first.exported_rows == 0
    assert first.report.status == "COLLECTING"
    assert second is None
    assert not (tmp_path / "model.json").exists()


def test_learning_pipeline_can_be_disabled(tmp_path):
    settings = PipelineSettings()
    settings.model_auto_evaluate_enabled = False
    settings.model_training_dataset_path = str(tmp_path / "training.csv")
    settings.model_output_path = str(tmp_path / "model.json")
    pipeline = LearningPipeline(settings, TradeJournal(tmp_path / "trades.db"))

    assert pipeline.maybe_run(datetime(2026, 7, 27, 18, 0, tzinfo=KST)) is None
    assert not (tmp_path / "training.csv").exists()
