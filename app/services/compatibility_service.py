"""
Day 6 — Compatibility Score.

A weighted combination of six signals already present on Intern/TeamHistory
(no new tables beyond what Days 1-3 already modeled). Each signal is first
normalized to 0.0-1.0, then combined with fixed weights into a single
0-100 score, with the per-signal breakdown always returned alongside the
total so the number is explainable rather than a black box.
"""
from itertools import combinations

from app import models
from app.services.skill_utils import intern_skill_names, skill_diversity_score

# Weights must sum to 1.0. Exposed as a module constant (rather than buried
# in the function) so they're easy to find and tune without touching logic.
COMPATIBILITY_WEIGHTS: dict[str, float] = {
    "communication": 0.20,
    "leadership": 0.15,
    "attendance": 0.15,
    "team_history": 0.15,
    "skill_diversity": 0.20,
    "github_activity": 0.15,
}

# Above this many GitHub contributions, the github_activity component is
# already at its maximum (1.0) — avoids one prolific outlier dominating the
# score, and keeps the scale meaningful for typical intern activity levels.
GITHUB_ACTIVITY_SATURATION_POINT = 200


def _soft_skill_component(score_a: float, score_b: float, scale_max: float = 10.0) -> float:
    """Shared shape for communication/leadership: rewards both interns
    scoring well AND scoring similarly (a strong communicator paired with a
    weak one is less "compatible" on that axis than two solid-but-average
    communicators), rather than just averaging the two raw scores."""
    avg = (score_a + score_b) / 2.0
    gap = abs(score_a - score_b)
    return max(0.0, (avg / scale_max) * (1 - gap / scale_max))


def _attendance_component(intern_a: models.Intern, intern_b: models.Intern) -> float:
    return ((intern_a.attendance_pct or 0.0) + (intern_b.attendance_pct or 0.0)) / 200.0


def _github_activity_component(intern_a: models.Intern, intern_b: models.Intern) -> float:
    avg_contributions = ((intern_a.github_contributions or 0) + (intern_b.github_contributions or 0)) / 2.0
    return min(avg_contributions / GITHUB_ACTIVITY_SATURATION_POINT, 1.0)


def _team_history_component(
    intern_a: models.Intern,
    intern_b: models.Intern,
    history_a: list[models.TeamHistory],
    history_b: list[models.TeamHistory],
) -> float:
    """1.0 = worked together before with great outcomes, 0.0 = worked
    together before with poor outcomes, 0.5 = no shared history on record
    (neutral — absence of data isn't evidence of poor compatibility)."""
    teams_a = {h.past_team_name: h.outcome_rating for h in history_a if h.past_team_name}
    shared_ratings = [
        (teams_a[h.past_team_name] + h.outcome_rating) / 2.0
        for h in history_b
        if h.past_team_name in teams_a and h.outcome_rating is not None
    ]
    if not shared_ratings:
        return 0.5
    return max(0.0, min(1.0, (sum(shared_ratings) / len(shared_ratings)) / 10.0))


def pairwise_compatibility(
    intern_a: models.Intern,
    intern_b: models.Intern,
    history_a: list[models.TeamHistory],
    history_b: list[models.TeamHistory],
) -> dict:
    """Returns {total_score (0-100), components: {name: {raw_0_1, weight,
    contribution}}} for one pair of interns."""
    components = {
        "communication": _soft_skill_component(
            intern_a.communication_score or 0.0, intern_b.communication_score or 0.0
        ),
        "leadership": _soft_skill_component(
            intern_a.leadership_score or 0.0, intern_b.leadership_score or 0.0
        ),
        "attendance": _attendance_component(intern_a, intern_b),
        "team_history": _team_history_component(intern_a, intern_b, history_a, history_b),
        "skill_diversity": skill_diversity_score(
            intern_skill_names(intern_a), intern_skill_names(intern_b)
        ),
        "github_activity": _github_activity_component(intern_a, intern_b),
    }

    breakdown = {}
    total = 0.0
    for name, raw in components.items():
        weight = COMPATIBILITY_WEIGHTS[name]
        contribution = raw * weight
        breakdown[name] = {
            "raw_score": round(raw, 4),
            "weight": weight,
            "contribution": round(contribution, 4),
        }
        total += contribution

    return {
        "intern_a_id": intern_a.id,
        "intern_b_id": intern_b.id,
        "total_score": round(total * 100, 2),
        "components": breakdown,
    }


def team_compatibility(members: list[models.Intern], history_by_intern: dict[int, list[models.TeamHistory]]) -> dict:
    """Average pairwise compatibility across every member pair on the team.
    Returns the overall score plus each pair's breakdown, so a team lead can
    see not just "72/100" but which pair is dragging it down."""
    if len(members) < 2:
        return {"member_count": len(members), "average_score": 0.0, "pairs": []}

    pairs = []
    for a, b in combinations(members, 2):
        pairs.append(
            pairwise_compatibility(
                a, b,
                history_by_intern.get(a.id, []),
                history_by_intern.get(b.id, []),
            )
        )

    average_score = round(sum(p["total_score"] for p in pairs) / len(pairs), 2)
    return {"member_count": len(members), "average_score": average_score, "pairs": pairs}
