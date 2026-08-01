from app.ml import success_probability_model
from app.services import explainability_service


def setup_function(_fn):
    # Ensure a clean, deterministic model/background/explainer for every test,
    # same pattern test_success_probability_service.py relies on implicitly.
    success_probability_model.reset_model()
    explainability_service._explainer = None


def test_explain_success_probability_returns_all_features():
    result = explainability_service.explain_success_probability(0.6, 85.0, 7.5)
    feature_names = {f["feature"] for f in result["factors"]}
    assert feature_names == {"team_balance", "avg_attendance_pct", "avg_feedback_score"}
    assert isinstance(result["base_value"], float)
    assert len(result["reasons"]) == 3
    assert isinstance(result["summary"], str) and result["summary"]


def test_explain_success_probability_is_deterministic():
    result_a = explainability_service.explain_success_probability(0.6, 85.0, 7.5)
    result_b = explainability_service.explain_success_probability(0.6, 85.0, 7.5)
    assert result_a == result_b


def test_strong_signals_produce_positive_directions():
    result = explainability_service.explain_success_probability(0.9, 99.0, 9.5)
    directions = {f["feature"]: f["direction"] for f in result["factors"]}
    assert all(d in ("increased", "neutral") for d in directions.values())
    assert any(d == "increased" for d in directions.values())


def test_weak_signals_produce_negative_directions():
    result = explainability_service.explain_success_probability(0.05, 20.0, 1.0)
    directions = {f["feature"]: f["direction"] for f in result["factors"]}
    assert all(d in ("decreased", "neutral") for d in directions.values())
    assert any(d == "decreased" for d in directions.values())


def test_reasons_are_ordered_by_impact_matching_summary():
    """Day 20 QA regression test: `reasons` used to be built in fixed
    feature-declaration order (team_balance, avg_attendance_pct,
    avg_feedback_score) regardless of which feature actually had the
    largest SHAP magnitude, so it could silently disagree with `summary`'s
    "strongest driver" claim. `reasons[0]` must always describe the same
    feature `summary` names as the top driver.
    """
    # A deliberately lopsided input where attendance/feedback are extreme
    # (near their max) while team_balance sits mid-range, so team_balance
    # is unlikely to be the top-impact feature — a case the old
    # fixed-order code would have gotten wrong.
    result = explainability_service.explain_success_probability(0.5, 99.0, 9.8)

    ranked_feature = max(result["factors"], key=lambda f: abs(f["shap_value"]))["feature"]
    top_label = explainability_service.FEATURE_LABELS[ranked_feature]

    assert top_label in result["summary"].lower()
    assert top_label in result["reasons"][0].lower()


def test_shap_values_sum_close_to_prediction_minus_base(monkeypatch):
    """Sanity check on the SHAP additivity property: base_value + sum(shap
    contributions) should reconstruct the model's own log-odds output for
    the same input (up to rounding)."""
    import numpy as np

    team_balance, attendance, feedback = 0.6, 85.0, 7.5
    result = explainability_service.explain_success_probability(team_balance, attendance, feedback)

    model = success_probability_model.get_model()
    X = np.array([[team_balance, attendance / 100.0, feedback / 10.0]])
    margin = float(model.decision_function(X)[0])

    reconstructed = result["base_value"] + sum(f["shap_value"] for f in result["factors"])
    assert abs(reconstructed - margin) < 0.01
