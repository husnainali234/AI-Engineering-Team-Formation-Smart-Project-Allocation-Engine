"""
Day 7 — Leadership Detection.

Hybrid rule-based scorer that picks a leader *within* a group. The groups
themselves come from team_formation_service's clustering engine — rules
decide "who leads", ML decides "who's on the team together". A well-
explained weighted rule beats a black-box classifier here for a concrete
reason: there's no labeled "was actually a good leader" outcome data yet
to train one on.
"""
from app import models
from app.services.skill_utils import intern_skill_names

# Weights must sum to 1.0.
LEADERSHIP_WEIGHTS: dict[str, float] = {
    "leadership_score": 0.40,
    "communication": 0.20,
    "team_history": 0.15,
    "contribution_consistency": 0.25,
}

# GitHub contributions above this are already at max (1.0) for the
# contribution-consistency component. Deliberately lower than
# compatibility_service's saturation point (200) — leadership is about
# steady, visible contribution, not raw volume, so it saturates early.
GITHUB_ACTIVITY_SATURATION_POINT = 50


def _leadership_component(intern: models.Intern) -> float:
    return max(0.0, min(1.0, (intern.leadership_score or 0.0) / 10.0))


def _communication_component(intern: models.Intern) -> float:
    return max(0.0, min(1.0, (intern.communication_score or 0.0) / 10.0))


def _team_history_component(history: list[models.TeamHistory]) -> float:
    """1.0 = strong track record on past teams, 0.5 = no history on record
    (neutral — absence of data isn't evidence of poor leadership)."""
    ratings = [h.outcome_rating for h in history if h.outcome_rating is not None]
    if not ratings:
        return 0.5
    return max(0.0, min(1.0, (sum(ratings) / len(ratings)) / 10.0))


def _contribution_consistency_component(intern: models.Intern) -> float:
    attendance_norm = max(0.0, min(1.0, (intern.attendance_pct or 0.0) / 100.0))
    github_norm = max(0.0, min(1.0, (intern.github_contributions or 0) / GITHUB_ACTIVITY_SATURATION_POINT))
    return 0.6 * attendance_norm + 0.4 * github_norm


def score_leadership(intern: models.Intern, history: list[models.TeamHistory]) -> dict:
    """Returns {total_score (0-100), components: {name: {raw_score, weight,
    contribution}}} for one intern."""
    components = {
        "leadership_score": _leadership_component(intern),
        "communication": _communication_component(intern),
        "team_history": _team_history_component(history),
        "contribution_consistency": _contribution_consistency_component(intern),
    }

    breakdown = {}
    total = 0.0
    for name, raw in components.items():
        weight = LEADERSHIP_WEIGHTS[name]
        contribution = raw * weight
        breakdown[name] = {
            "raw_score": round(raw, 4),
            "weight": weight,
            "contribution": round(contribution, 4),
        }
        total += contribution

    return {
        "total_score": round(max(0.0, min(100.0, total * 100)), 2),
        "components": breakdown,
    }


def rank_leadership(
    members: list[models.Intern],
    history_by_intern: dict[int, list[models.TeamHistory]],
) -> list[dict]:
    """Every member scored, sorted by total_score descending, ties broken
    by intern id ascending (fully deterministic)."""
    ranked = []
    for member in members:
        result = score_leadership(member, history_by_intern.get(member.id, []))
        ranked.append(
            {
                "intern_id": member.id,
                "full_name": member.full_name,
                "total_score": result["total_score"],
                "components": result["components"],
            }
        )
    ranked.sort(key=lambda r: (-r["total_score"], r["intern_id"]))
    return ranked


def suggest_leader(
    members: list[models.Intern],
    history_by_intern: dict[int, list[models.TeamHistory]],
) -> dict:
    """The single top-ranked member — raises if the team/group is empty."""
    if not members:
        raise ValueError("Cannot suggest a leader for an empty group of members")
    return rank_leadership(members, history_by_intern)[0]


def team_skill_breadth(intern: models.Intern) -> int:
    """Count of distinct skills/technologies this intern has — used by
    workload_service as a proxy for 'who can ramp up fastest' on an
    unmatched required skill."""
    return len(intern_skill_names(intern))
