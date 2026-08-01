"""
Day 11 — Explainable AI Layer.

Wraps the Day 9 success-probability model (a scikit-learn LogisticRegression,
see app/ml/success_probability_model.py) with a SHAP explainer, then turns
the raw SHAP values into plain-English sentences a mentor can read without
knowing what SHAP is.

Why SHAP + LinearExplainer specifically, not KernelExplainer/TreeExplainer:
the underlying model is a plain linear model (logistic regression on 3
features), so shap.LinearExplainer gives an exact, closed-form attribution
(coefficient × (value - background mean)) instead of the sampling-based
approximation KernelExplainer would need for an arbitrary black-box model.
Exact + deterministic + fast beats "more general" here, since the model
really is linear — same "simplest tool that satisfies the requirement"
reasoning used throughout this project (Day 7's round-robin, Day 8's greedy
workload assignment).

Why a fixed background sample (app.ml.success_probability_model's
get_background_sample), not the single mean row: SHAP's interventional
LinearExplainer technically supports either, but using a sample of the
same synthetic training distribution — rather than collapsing it to one
mean point — is what SHAP's own documentation recommends for stable,
representative "typical team" baselines, and it costs nothing extra since
that sample is itself cached process-wide.
"""
import numpy as np
import shap

from app.ml import success_probability_model

_explainer: "shap.LinearExplainer | None" = None

# Human-readable labels + short descriptions for each of the model's three
# input features — keeps the generated sentences readable without leaking
# the underlying column names (team_balance, avg_attendance_pct, ...) into
# mentor-facing text.
FEATURE_LABELS: dict[str, str] = {
    "team_balance": "team skill balance",
    "avg_attendance_pct": "average attendance",
    "avg_feedback_score": "average mentor feedback",
}

# Below this magnitude, a factor's effect on the prediction is treated as
# negligible rather than worth a sentence of its own — keeps the reason
# list focused on what actually moved the number.
_NEGLIGIBLE_SHAP_THRESHOLD = 0.01


def _get_explainer() -> "shap.LinearExplainer":
    global _explainer
    if _explainer is None:
        model = success_probability_model.get_model()
        # 100 matches shap's own default max_samples for an Independent
        # masker built from raw background data — requesting exactly that
        # many avoids an internal, log-noisy re-subsampling step.
        background = success_probability_model.get_background_sample(sample_size=100)
        _explainer = shap.LinearExplainer(model, background)
    return _explainer


def _direction_word(shap_value: float) -> str:
    if shap_value > _NEGLIGIBLE_SHAP_THRESHOLD:
        return "increased"
    if shap_value < -_NEGLIGIBLE_SHAP_THRESHOLD:
        return "decreased"
    return "had little effect on"


def _feature_reason(feature: str, raw_value: float, shap_value: float) -> str:
    label = FEATURE_LABELS.get(feature, feature)
    direction = _direction_word(shap_value)

    if feature == "avg_attendance_pct":
        display_value = f"{raw_value * 100:.0f}%"
    elif feature == "avg_feedback_score":
        display_value = f"{raw_value * 10:.1f}/10"
    else:
        display_value = f"{raw_value:.2f}"

    return f"{label.capitalize()} ({display_value}) {direction} the predicted success probability."


def _summary(reasons_by_impact: list[tuple[str, float]]) -> str:
    if not reasons_by_impact:
        return "No single factor stood out — the prediction sits close to the model's baseline."

    top_feature, top_shap = reasons_by_impact[0]
    label = FEATURE_LABELS.get(top_feature, top_feature)
    direction = "the strongest positive driver" if top_shap > 0 else "the biggest drag"
    return f"{label.capitalize()} was {direction} behind this team's success probability."


def explain_success_probability(team_balance: float, avg_attendance_pct: float, avg_feedback_score: float) -> dict:
    """Returns {base_value, factors: [{feature, value, shap_value,
    direction}], summary, reasons: [str, ...]} for one team's success
    probability prediction — the "explanation" field attached to
    /success-probability and, since it's the same signal, to each team in
    /recommend-teams.

    base_value / shap_value are in the model's log-odds (margin) space,
    which is what LinearExplainer explains for a linear classifier — the
    sign and relative magnitude are what matters for the reasons text, not
    the raw units, so this is never surfaced as if it were a probability.
    """
    explainer = _get_explainer()
    normalized = [team_balance, avg_attendance_pct / 100.0, avg_feedback_score / 10.0]
    shap_values = explainer.shap_values(np.array([normalized]))[0]
    base_value = float(explainer.expected_value)

    features = success_probability_model.FEATURE_NAMES
    factors = []
    for feature, raw_value, shap_value in zip(features, normalized, shap_values):
        factors.append(
            {
                "feature": feature,
                "value": round(float(raw_value), 4),
                "shap_value": round(float(shap_value), 4),
                "direction": _direction_word(float(shap_value)).replace("had little effect on", "neutral"),
            }
        )

    ranked = sorted(zip(features, (float(v) for v in shap_values)), key=lambda kv: abs(kv[1]), reverse=True)

    # Day 20 QA fix: `reasons` used to be built in fixed feature-declaration
    # order (team_balance, avg_attendance_pct, avg_feedback_score), which
    # could silently disagree with `summary`'s "strongest driver" claim
    # whenever a different feature actually had the largest SHAP magnitude
    # — e.g. summary would correctly name attendance as the top factor while
    # reasons[0] still talked about team_balance. Reasons are now built from
    # the same `ranked`-by-impact order summary already uses, so the two
    # never contradict each other.
    raw_by_feature = dict(zip(features, normalized))
    reasons = [_feature_reason(f, raw_by_feature[f], s) for f, s in ranked]

    return {
        "base_value": round(base_value, 4),
        "factors": factors,
        "summary": _summary(ranked),
        "reasons": reasons,
    }
