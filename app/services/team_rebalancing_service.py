"""
Day 16 — Bonus Feature (Engineer A): Automatic Team Rebalancing.

"Re-run the engine when a member becomes unavailable": find the best-fit
replacement for a departing member from the unassigned candidate pool,
then rescore the team exactly the way a freshly-formed one would be
scored, reusing recommend_teams_service.compute_team_recommendation (Day
10) rather than inventing a second scoring path that could drift from it.

Deliberately DB-free, same as recommend_teams_service and
team_formation_service — everything here takes already-loaded
models.Team / models.Intern objects and returns plain dicts, so it's
unit-testable without a live Session. app/routers/team_rebalancing.py
owns the query/persistence side.
"""
from dataclasses import dataclass
from typing import Optional

from app import models
from app.services.matching_service import cosine_similarity


def teams_needing_rebalance(teams: list[models.Team]) -> list[dict]:
    """Teams (already loaded with members -> intern) that have at least
    one member whose Intern.is_available is False — the "member becomes
    unavailable" trigger the guide asks for. Surfaced as a list to review
    and act on via POST /rebalance/team/{id}, rather than an automatic,
    silent side-effect of PATCH /interns/{id}: swapping a real person off
    a team is consequential enough that a mentor should see who's being
    proposed as the replacement before it happens (see DAY16_GUIDE.md)."""
    flagged = []
    for team in teams:
        unavailable = [m for m in team.members if m.intern is not None and not m.intern.is_available]
        if unavailable:
            flagged.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "unavailable_members": [
                        {"intern_id": m.intern_id, "full_name": m.intern.full_name} for m in unavailable
                    ],
                }
            )
    return flagged


@dataclass
class ReplacementSuggestion:
    departing_intern_id: int
    departing_intern_name: str
    replacement_intern_id: Optional[int]
    replacement_intern_name: Optional[str]
    similarity_score: Optional[float]
    reason: str


def find_replacement(
    departing: models.Intern, candidates: list[models.Intern]
) -> ReplacementSuggestion:
    """Best-fit replacement = highest skill-embedding cosine similarity to
    the departing member among available/unassigned/embedded candidates.
    Minimizes disruption to whatever the team was actually assembled for
    (Day 7's clustering already used the same embeddings to decide who
    belonged together), rather than picking arbitrarily or by seniority.
    Ties broken by intern id ascending — fully deterministic, same
    convention as leadership_service.rank_leadership."""
    usable = [c for c in candidates if c.skill_embedding and c.id != departing.id]
    if not usable or not departing.skill_embedding:
        return ReplacementSuggestion(
            departing_intern_id=departing.id,
            departing_intern_name=departing.full_name,
            replacement_intern_id=None,
            replacement_intern_name=None,
            similarity_score=None,
            reason="No available, unassigned, embedded candidate found to replace this member.",
        )

    scored = [(c, cosine_similarity(departing.skill_embedding, c.skill_embedding)) for c in usable]
    scored.sort(key=lambda pair: (-pair[1], pair[0].id))
    best, score = scored[0]

    return ReplacementSuggestion(
        departing_intern_id=departing.id,
        departing_intern_name=departing.full_name,
        replacement_intern_id=best.id,
        replacement_intern_name=best.full_name,
        similarity_score=round(score, 4),
        reason=(
            f"Closest skill-profile match to {departing.full_name} among available, "
            f"unassigned candidates (skill-embedding cosine similarity {round(score, 4)})."
        ),
    )


def plan_rebalance(
    unavailable_members: list[models.Intern], candidate_pool: list[models.Intern]
) -> list[ReplacementSuggestion]:
    """Suggests a replacement for each unavailable member in turn, removing
    each chosen replacement from the pool before considering the next —
    a team losing two members at once should get two *different*
    replacements, not the same top candidate suggested twice."""
    pool = list(candidate_pool)
    suggestions = []
    for departing in unavailable_members:
        suggestion = find_replacement(departing, pool)
        suggestions.append(suggestion)
        if suggestion.replacement_intern_id is not None:
            pool = [c for c in pool if c.id != suggestion.replacement_intern_id]
    return suggestions
