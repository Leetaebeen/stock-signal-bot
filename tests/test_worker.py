from app.worker import run_forever


def test_worker_exports_run_forever():
    assert callable(run_forever)
