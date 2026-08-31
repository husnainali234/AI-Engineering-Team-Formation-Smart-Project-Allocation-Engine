"""
Day 17 — tests for app/ml/mlflow_tracking.py.

Scope: the tracking helper itself (params/metrics/tag logging against a
local file store, and the "never raises" guarantee), not the success-
probability model's predictions — those are already covered by
test_success_probability_service.py. `_disable_mlflow_tracking` in
conftest.py is overridden locally (via monkeypatch) so these tests can
exercise the real logging path against a throwaway tmp_path directory.
"""
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app.config import settings
from app.ml import mlflow_tracking


@pytest.fixture()
def enabled_tracking(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_ENABLED", True)
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", f"file:{tmp_path / 'mlruns'}")
    monkeypatch.setattr(settings, "MLFLOW_EXPERIMENT_NAME", "test-success-probability")
    return tmp_path


def _fit_dummy_model():
    X = np.array([[0.1, 0.5, 0.2], [0.9, 0.8, 0.9], [0.2, 0.4, 0.3], [0.8, 0.9, 0.7]])
    y = np.array([0, 1, 0, 1])
    model = LogisticRegression().fit(X, y)
    return model, X, y


def test_disabled_by_default_in_tests():
    """The autouse conftest fixture turns tracking off; calling the logger
    with it off must be a pure no-op (no mlruns dir, no exception)."""
    model, X, y = _fit_dummy_model()
    mlflow_tracking.log_success_probability_training(
        model, X, y, params={"random_seed": 42, "n_synthetic_samples": 10}
    )
    # No assertion needed beyond "didn't raise" — MLFLOW_TRACKING_ENABLED
    # is False here (conftest default), so log_success_probability_training
    # returns immediately.


def test_logs_run_with_params_metrics_and_version_tag(enabled_tracking):
    import mlflow

    model, X, y = _fit_dummy_model()
    params = {"random_seed": 42, "n_synthetic_samples": 2000, "feature_names": "a,b,c"}

    mlflow_tracking.log_success_probability_training(model, X, y, params=params)

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    experiment = mlflow.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)
    assert experiment is not None

    runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])
    assert len(runs) == 1

    run = runs.iloc[0]
    assert run["params.random_seed"] == "42"
    assert run["params.n_synthetic_samples"] == "2000"
    assert "metrics.train_accuracy" in runs.columns
    assert 0.0 <= run["metrics.train_accuracy"] <= 1.0
    assert run["tags.model_type"] == "LogisticRegression"
    assert len(run["tags.model_version"]) == 12  # short hex fingerprint


def test_version_tag_is_deterministic_for_same_params(enabled_tracking):
    import mlflow

    model, X, y = _fit_dummy_model()
    params = {"random_seed": 42, "n_synthetic_samples": 2000}

    mlflow_tracking.log_success_probability_training(model, X, y, params=params)
    mlflow_tracking.log_success_probability_training(model, X, y, params=params)

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    experiment = mlflow.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)
    runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])

    assert len(runs) == 2
    tags = set(runs["tags.model_version"])
    assert len(tags) == 1  # same params -> same fingerprint every time


def test_version_tag_differs_for_different_params(enabled_tracking):
    import mlflow

    model, X, y = _fit_dummy_model()
    mlflow_tracking.log_success_probability_training(
        model, X, y, params={"random_seed": 42, "n_synthetic_samples": 2000}
    )
    mlflow_tracking.log_success_probability_training(
        model, X, y, params={"random_seed": 7, "n_synthetic_samples": 2000}
    )

    mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
    experiment = mlflow.get_experiment_by_name(settings.MLFLOW_EXPERIMENT_NAME)
    runs = mlflow.search_runs(experiment_ids=[experiment.experiment_id])

    tags = set(runs["tags.model_version"])
    assert len(tags) == 2  # different params -> different fingerprint


def test_never_raises_when_tracking_backend_is_broken(enabled_tracking, monkeypatch, tmp_path):
    """A tracking-store failure must not propagate — training/serving the
    model matters more than logging it. Forces a real failure by pointing
    the tracking URI at a path *under a plain file* (not a directory), so
    MLflow can't create the run store no matter what user this runs as."""
    blocker_file = tmp_path / "blocker"
    blocker_file.write_text("not a directory")
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", f"file:{blocker_file}/mlruns")
    model, X, y = _fit_dummy_model()

    # Must not raise.
    mlflow_tracking.log_success_probability_training(
        model, X, y, params={"random_seed": 42, "n_synthetic_samples": 2000}
    )
