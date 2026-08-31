"""
Day 10 — Checkpoint 2: per-team recommendation computation.

This is the pure, DB-free half of the `/recommend-teams` integration layer
(see app/routers/recommend_teams.py for the persistence/orchestration half
that needs a Session). Given a team's members plus the same
history/feedback/project inputs Days 4-9's individual engines already take,
`compute_team_recommendation` runs every engine once and folds the results
into a single dict, so the router doesn't have to know the internals of six
different services.

Why this stays a plain function instead of a class/pipeline object: every
engine it calls is already a plain function taking plain models — there's
no shared mutable state across steps, so a pipeline abstraction would add
indirection without buying anything. Keeping it here (not inline in the
router) is what makes it unit-testable against `db_session`-built models
without spinning up a TestClient or hitting real HTTP routes.
"""
from app import models
from app.services import (
    compatibility_service,
    project_recommendation_service,
    risk_analysis_service,
    skill_matrix_service,
    success_probability_service,
)
from app.services.matching_service import team_diversity

# Blends four already-0-100 (or 0-1, scaled below) signals into one overall
# score for ranking/display. Must sum to 1.0 — enforced by
# test_overall_score_weights_sum_to_one so the number stays interpretable
# as "a weighted percentage" rather than drifting out of 0-100 bounds.
OVERALL_SCORE_WEIGHTS: dict[str, float] = {
    "compatibility": 0.35,
    "success_probability": 0.35,
    "project_fit": 0.20,
    "skill_diversity": 0.10,
}


def _best_project_fit(members: list[models.Intern], projects: list[models.Project]) -> dict | None:
    """Highest-coverage project for this team, or None if there are no
    projects to recommend against yet (a team can exist before any project
    has been entered — coverage against nothing isn't a meaningful score)."""
    if not projects:
        return None
    ranked = project_recommendation_service.recommend_projects(members, projects)
    return ranked[0] if ranked else None


def _overall_score(
    compatibility_score: float,
    success_probability: float,
    project_fit: dict | None,
    diversity_score: float,
) -> float:
    project_component = (project_fit["coverage_score"] * 100.0) if project_fit else 0.0
    total = (
        compatibility_score * OVERALL_SCORE_WEIGHTS["compatibility"]
        + success_probability * OVERALL_SCORE_WEIGHTS["success_probability"]
        + project_component * OVERALL_SCORE_WEIGHTS["project_fit"]
        + (diversity_score * 100.0) * OVERALL_SCORE_WEIGHTS["skill_diversity"]
    )
    return round(max(0.0, min(100.0, total)), 2)


def compute_team_recommendation(
    members: list[models.Intern],
    history_by_intern: dict[int, list[models.TeamHistory]],
    feedback_by_intern: dict[int, list["models.MentorFeedback"]],
    projects: list[models.Project],
) -> dict:
    """Runs compatibility (Day 6), skill matrix (Day 4), project fit
    (Day 8), success probability (Day 9), and risk analysis (Day 9) for one
    team's members, then blends the results into an overall_score.

    Returns:
        {
            "compatibility_score": float (0-100),
            "skill_matrix": list[dict]   (rows matching SkillMatrixRowOut),
            "project_fit": dict | None   (matching ProjectFitOut, or None),
            "success_probability": float (0-100),
            "risks": list[dict]          (rows matching RiskOut),
            "overall_score": float (0-100),
            "explanation": dict          (matching ExplanationOut — Day 11 SHAP explanation),
        }
    """
    diversity_score = team_diversity(members)

    compatibility_result = compatibility_service.team_compatibility(members, history_by_intern)
    compatibility_score = compatibility_result["average_score"]

    skill_matrix = skill_matrix_service.build_skill_matrix(members)

    project_fit = _best_project_fit(members, projects)

    success_result = success_probability_service.compute_success_probability(members, feedback_by_intern)
    success_probability = success_result["success_probability"]

    risks = risk_analysis_service.assess_risks(
        members,
        compatibility_score=compatibility_score,
        diversity_score=diversity_score,
    )

    overall_score = _overall_score(compatibility_score, success_probability, project_fit, diversity_score)

    return {
        "compatibility_score": compatibility_score,
        "skill_matrix": skill_matrix,
        "project_fit": project_fit,
        "success_probability": success_probability,
        "risks": risks,
        "overall_score": overall_score,
        # Day 11: same SHAP-based explanation success_probability_service
        # already attaches to /success-probability — surfaced here too so
        # every /recommend-teams team carries its own "why" (Architecture
        # doc: "SHAP-based reasons attached to every recommendation").
        "explanation": success_result["explanation"],
    }
