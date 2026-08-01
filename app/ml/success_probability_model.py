"""
Day 9 — Success Probability baseline model.

There's no real "did this team succeed" outcome data yet, so this trains on
*synthesized* historical outcomes instead — using exactly the three signals
the spec calls out: team balance (Day 7's diversity score), attendance, and
mentor feedback. Lazily trained on first use and cached in-process, the
same lazy-singleton pattern as app/ml/embedding_model.py, so the (trivial)
training cost never happens at process start or during test collection.

Why LogisticRegression on a synthetic dataset, not a hand-written formula:
the spec explicitly asks for a trained scikit-learn model, not a rule-based
score (that's what Risk Analysis is for, right below this). A logistic
regression trained on synthetic labels sampled from a simple, explainable
prior gives a genuine probabilistic model — predict_proba, not a threshold
— while staying fully deterministic and easy to describe to a mentor: "the
model learned that balanced, well-attended, well-reviewed teams succeed
more often," because that's exactly the prior it was trained on.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression

from app.ml.mlflow_tracking import log_success_probability_training

_RANDOM_SEED = 42
_N_SYNTHETIC_SAMPLES = 2000

_model: LogisticRegression | None = None
_background_sample: np.ndarray | None = None

# Order must match the column order _generate_synthetic_training_data /
# predict_success_probability build X in — shared with Day 11's
# explainability_service so SHAP values line up with the right feature name.
FEATURE_NAMES: list[str] = ["team_balance", "avg_attendance_pct", "avg_feedback_score"]


def _generate_synthetic_training_data(n: int = _N_SYNTHETIC_SAMPLES, seed: int = _RANDOM_SEED):
    """Synthesized historical outcomes. Each row is one hypothetical past
    team: (team_balance, attendance, feedback) -> did it succeed. The
    weights below are a deliberately simple, explainable prior — not fit to
    any real data, since none exists yet — reflecting that more balanced,
    more consistently present, and better-reviewed teams tend to succeed
    more often."""
    rng = np.random.default_rng(seed)

    diversity = rng.uniform(0.0, 1.0, n)
    attendance = rng.uniform(0.4, 1.0, n)
    feedback = rng.uniform(0.0, 1.0, n)

    signal = 0.35 * diversity + 0.30 * attendance + 0.35 * feedback
    noise = rng.normal(0.0, 0.12, n)
    probability = np.clip(signal + noise, 0.0, 1.0)

    # Binarize via a coin flip at that probability, so the classifier
    # learns a genuine probabilistic mapping instead of memorizing a
    # deterministic threshold.
    outcome = rng.binomial(1, probability)

    X = np.column_stack([diversity, attendance, feedback])
    return X, outcome


def _get_model() -> LogisticRegression:
    global _model
    if _model is None:
        X, y = _generate_synthetic_training_data()
        model = LogisticRegression(random_state=_RANDOM_SEED)
        model.fit(X, y)
        _model = model

        # Day 17: lightweight MLflow tracking — best-effort, never raises.
        log_success_probability_training(
            model, X, y,
            params={
                "random_seed": _RANDOM_SEED,
                "n_synthetic_samples": _N_SYNTHETIC_SAMPLES,
                "feature_names": ",".join(FEATURE_NAMES),
                "model_class": "LogisticRegression",
            },
        )
    return _model


def predict_success_probability(team_balance: float, avg_attendance_pct: float, avg_feedback_score: float) -> float:
    """team_balance: 0.0-1.0 (Day 7/6 diversity score). avg_attendance_pct:
    0-100. avg_feedback_score: 0-10. Returns a 0.0-1.0 success probability."""
    model = _get_model()
    X = np.array([[team_balance, avg_attendance_pct / 100.0, avg_feedback_score / 10.0]])
    return float(model.predict_proba(X)[0][1])


def get_model() -> LogisticRegression:
    """Public accessor for the trained model — used by
    app.services.explainability_service to build a SHAP LinearExplainer
    without duplicating the lazy-singleton training logic."""
    return _get_model()


def get_background_sample(sample_size: int = 200) -> np.ndarray:
    """A fixed-seed subsample of the same synthetic training data the
    model itself was fit on, for SHAP's LinearExplainer to use as its
    reference distribution ('what does a typical team look like'). Cached
    process-wide and deterministic — same reasoning as _get_model's
    singleton: this only needs to happen once, and needs to be stable so
    the same inputs always produce the same SHAP breakdown."""
    global _background_sample
    if _background_sample is None:
        X, _ = _generate_synthetic_training_data()
        rng = np.random.default_rng(_RANDOM_SEED)
        idx = rng.choice(len(X), size=min(sample_size, len(X)), replace=False)
        _background_sample = X[idx]
    return _background_sample


def reset_model() -> None:
    """Test hook — forces retraining (from the same fixed seed) on the
    next predict call."""
    global _model, _background_sample
    _model = None
    _background_sample = None
