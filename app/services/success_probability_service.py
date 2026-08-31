"""
Day 9 — Success Probability.

Feeds the three signals the spec calls out — team balance, attendance,
feedback — into the lazily-trained baseline model in
app/ml/success_probability_model.py and returns a 0-100% probability
alongside the underlying feature values, so a mentor can see *why* a team
scored the way it did, not just the number.
"""
from app import models
from app.ml.success_probability_model import predict_success_probability
from app.services import explainability_service
from app.services.matching_service import team_diversity

# 0-10 midpoint — used when a member has no mentor feedback on record yet.
# Same "absence of data isn't evidence" reasoning as leadership_service's
# neutral team_history default (0.5 there, on a 0-1 scale).
NEUTRAL_FEEDBACK_SCORE = 5.0


def _avg_attendance(members: list[models.Intern]) -> float:
    if not members:
        return 0.0
    return sum((m.attendance_pct or 0.0) for m in members) / len(members)


def _avg_feedback(
    members: list[models.Intern],
    feedback_by_intern: dict[int, list[models.MentorFeedback]],
) -> float:
    if not members:
        return NEUTRAL_FEEDBACK_SCORE

    per_member_scores = []
    for member in members:
        entries = feedback_by_intern.get(member.id, [])
        scores = [f.score for f in entries if f.score is not None]
        per_member_scores.append(sum(scores) / len(scores) if scores else NEUTRAL_FEEDBACK_SCORE)
    return sum(per_member_scores) / len(per_member_scores)


def compute_success_probability(
    members: list[models.Intern],
    feedback_by_intern: dict[int, list[models.MentorFeedback]],
) -> dict:
    """Returns {success_probability (0-100), features: {team_balance,
    avg_attendance_pct, avg_feedback_score}}."""
    if not members:
        return {
            "success_probability": 0.0,
            "features": {"team_balance": 0.0, "avg_attendance_pct": 0.0, "avg_feedback_score": 0.0},
            "explanation": {
                "base_value": 0.0,
                "factors": [],
                "summary": "No members to evaluate.",
                "reasons": [],
            },
        }

    balance = team_diversity(members)
    avg_attendance = _avg_attendance(members)
    avg_feedback = _avg_feedback(members, feedback_by_intern)

    probability = predict_success_probability(balance, avg_attendance, avg_feedback)
    explanation = explainability_service.explain_success_probability(balance, avg_attendance, avg_feedback)

    return {
        "success_probability": round(probability * 100, 2),
        "features": {
            "team_balance": round(balance, 4),
            "avg_attendance_pct": round(avg_attendance, 2),
            "avg_feedback_score": round(avg_feedback, 2),
        },
        "explanation": explanation,
    }
