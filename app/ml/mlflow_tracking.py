"""
Day 17 — lightweight MLflow model-version tracking.

Scope, deliberately narrow: there is exactly one trained model in this
system (Day 9's `success_probability_model`'s `LogisticRegression`, lazily
fit on synthetic data — see that module's docstring). This wraps that one
training call with an MLflow run: params (random seed, sample size,
feature names), metrics (train accuracy on the synthetic set), and a
"model_version" tag derived from a hash of the params/feature-name
combination, so a run can be told apart from a future run trained with
different synthetic-data assumptions without hand-bumping a version
number every time someone tweaks `_N_SYNTHETIC_SAMPLES`.

No tracking *server* is introduced — `MLFLOW_TRACKING_URI` defaults to a
local `file:./mlruns` store (see app/config.py), so `docker-compose up`
gets run history for free with no new service, no new port, and nothing
else in docker-compose.yml to keep healthy. Point the same env var at a
real tracking server later and nothing here changes.

Tracking is best-effort by construction: `log_success_probability_training`
never raises. A model that trains successfully but fails to log to MLflow
(disk full, unwritable volume, whatever) must not turn into a 500 on the
first `/success-probability` call — the model is the product; MLflow is
observability on top of it. Every failure path is caught and logged as a
warning instead of propagated. `MLFLOW_TRACKING_ENABLED=false` (set in the
test suite via monkeypatch — see tests/test_mlflow_tracking.py) skips
tracking entirely, keeping the test suite from touching disk for it.
"""
import hashlib
import logging

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


def _model_version_tag(params: dict) -> str:
    """Short, deterministic fingerprint of the training params — cheap
    stand-in for a real version number, stable as long as the training
    assumptions (seed, sample size, feature set) don't change."""
    raw = "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def log_success_probability_training(model, X: np.ndarray, y: np.ndarray, params: dict) -> None:
    """Log one training run of the success-probability model to MLflow.

    `model` is the already-fit LogisticRegression; `X`/`y` are the
    synthetic training set it was fit on (used only to compute a train
    accuracy metric here, not re-fit); `params` are the hyperparameters/
    data-generation settings worth recording (random_seed, n_samples,
    feature_names). Swallows and logs any exception rather than raising —
    see module docstring.
    """
    if not settings.MLFLOW_TRACKING_ENABLED:
        return

    try:
        import mlflow  # deferred import — same reasoning as sentence-transformers
                        # in embedding_model.py: keep it off the hot import path
                        # for requests that never train/retrain the model.

        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)

        train_accuracy = float(model.score(X, y))
        version_tag = _model_version_tag(params)

        with mlflow.start_run(run_name=f"success-probability-{version_tag}"):
            mlflow.log_params(params)
            mlflow.log_metric("train_accuracy", train_accuracy)
            mlflow.set_tag("model_version", version_tag)
            mlflow.set_tag("model_type", type(model).__name__)
    except Exception:  # noqa: BLE001 — tracking must never break training/serving
        logger.warning("MLflow tracking failed; continuing without it", exc_info=True)
