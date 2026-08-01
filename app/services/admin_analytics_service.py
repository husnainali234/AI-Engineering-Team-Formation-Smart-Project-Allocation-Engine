"""
Day 13 — Admin analytics aggregation.

Three of the four views the execution guide asks for; the fourth
(technology distribution) is deliberately NOT duplicated here — it's
already exactly Day 4's GET /skill-matrix/technology-frequency called
with no team_id (org-wide scope). Admin dashboard just calls that
existing endpoint directly, same reuse-over-duplicate call the Mentor
Dashboard made on Day 12 for pairwise compatibility.

Design note shared by all three functions below: Team.compatibility_score
and Team.success_probability default to 0.0 (see app/models.py) for a team
that was created via the plain CRUD endpoint and never run through the
Day 6/Day 9 engines (or POST /recommend-teams, which sets both). Averaging
those untouched 0.0s in with genuinely-scored teams would silently drag
every org-wide average toward zero as soon as an admin creates a team by
hand. So each function here distinguishes "scored" (score != 0.0) from
"unscored" and only averages over the scored subset — the unscored count
is still surfaced, just not blended into the average.

Day 15 checkpoint fix — scale mismatch: Team.compatibility_score is
persisted 0-100, but Team.success_probability is persisted 0-1 (see
app/models.py; both /recommend-teams and /success-probability/team/{id}/
recalculate divide the engine's 0-100 output by 100 before writing it,
deliberately, per the Day 1 ERD). Every *other* consumer of success
probability — the Day 9 SuccessProbabilityOut response, the Day 10
RecommendedTeamOut response, the Mentor Dashboard — reads it straight off
the live engine output (0-100) and never touches the persisted column. This
module was the first to read the persisted column back out for display,
and originally passed the raw 0-1 value straight through — which the Admin
Dashboard's `f"{value:.0f}%"` formatting (written against the 0-100
convention every other screen uses) would have rendered as "1%" instead of
"~72%" for anything but a placeholder score. Rescaled to 0-100 here so the
column's storage convention stays an implementation detail that doesn't
leak into what any endpoint returns.
"""
from statistics import mean

from app import models

# Team.success_probability is persisted 0-1 (see module docstring); every
# API response in this system reports success probability on a 0-100
# scale, so reads rescale by this factor. Named/imported rather than a
# bare `* 100` so a future column-scale change only needs an update here.
SUCCESS_PROBABILITY_DB_TO_PCT = 100.0


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 2) if values else None


def cross_team_analytics(teams: list[models.Team]) -> dict:
    """Org-wide rollup over every team: size distribution, average
    compatibility/success scores (scored teams only — see module
    docstring), and how many teams have a project and a risk assessment."""
    team_count = len(teams)
    sizes = [len(t.members) for t in teams]

    size_distribution: dict[str, int] = {}
    for size in sizes:
        key = str(size)
        size_distribution[key] = size_distribution.get(key, 0) + 1

    scored_compatibility = [t.compatibility_score for t in teams if t.compatibility_score]
    scored_success = [
        t.success_probability * SUCCESS_PROBABILITY_DB_TO_PCT for t in teams if t.success_probability
    ]

    teams_with_project = sum(1 for t in teams if t.project_id is not None)
    teams_assessed_for_risk = sum(1 for t in teams if t.risk_notes)
    teams_flagged_at_risk = sum(
        1 for t in teams if t.risk_notes and t.risk_notes != "No risks identified."
    )

    team_summaries = [
        {
            "team_id": t.id,
            "team_name": t.name,
            "member_count": len(t.members),
            "compatibility_score": t.compatibility_score or 0.0,
            "success_probability": (t.success_probability or 0.0) * SUCCESS_PROBABILITY_DB_TO_PCT,
            "project_title": t.project.title if t.project else None,
            "risk_assessed": bool(t.risk_notes),
            "flagged_at_risk": bool(t.risk_notes and t.risk_notes != "No risks identified."),
        }
        for t in teams
    ]

    return {
        "team_count": team_count,
        "avg_team_size": _avg([float(s) for s in sizes]) or 0.0,
        "size_distribution": size_distribution,
        "avg_compatibility_score": _avg(scored_compatibility),
        "avg_success_probability": _avg(scored_success),
        "teams_with_project": teams_with_project,
        "teams_without_project": team_count - teams_with_project,
        "teams_assessed_for_risk": teams_assessed_for_risk,
        "teams_flagged_at_risk": teams_flagged_at_risk,
        "teams": team_summaries,
    }


def project_success_rates(projects: list[models.Project]) -> dict:
    """Per-project rollup: how many teams have been matched to it, and how
    those teams are scoring — the answer to "which projects are we
    actually placing teams into successfully"."""
    project_rows = []
    projects_without_teams = 0

    for project in projects:
        teams = project.teams
        if not teams:
            projects_without_teams += 1

        scored_success = [
            t.success_probability * SUCCESS_PROBABILITY_DB_TO_PCT for t in teams if t.success_probability
        ]
        scored_compatibility = [t.compatibility_score for t in teams if t.compatibility_score]

        project_rows.append({
            "project_id": project.id,
            "title": project.title,
            "difficulty_level": project.difficulty_level,
            "team_count": len(teams),
            "avg_success_probability": _avg(scored_success),
            "avg_compatibility_score": _avg(scored_compatibility),
        })

    # Projects with the most teams (i.e. most in-demand) first; ties broken
    # by highest average success probability, unscored (None) sorting last.
    project_rows.sort(
        key=lambda r: (r["team_count"], r["avg_success_probability"] or -1.0),
        reverse=True,
    )

    return {
        "project_count": len(projects),
        "projects_without_teams": projects_without_teams,
        "projects": project_rows,
    }


def resource_utilization(interns: list[models.Intern], assigned_intern_ids: set[int]) -> dict:
    """Org-wide headcount view: how much of the intern pool is already
    committed to a team versus still sitting in the candidate pool for the
    next Team Formation run, plus a few data-readiness/quality signals
    (attendance, embedding coverage) an admin would want on one screen."""
    total = len(interns)
    assigned = sum(1 for i in interns if i.id in assigned_intern_ids)
    available = sum(1 for i in interns if i.is_available)
    available_and_unassigned = sum(
        1 for i in interns if i.is_available and i.id not in assigned_intern_ids
    )
    with_embedding = sum(1 for i in interns if i.skill_embedding is not None)

    return {
        "total_interns": total,
        "assigned_count": assigned,
        "unassigned_count": total - assigned,
        "assigned_pct": round(100.0 * assigned / total, 2) if total else 0.0,
        "available_count": available,
        "unavailable_count": total - available,
        "available_and_unassigned_count": available_and_unassigned,
        "with_embedding_count": with_embedding,
        "avg_attendance_pct": _avg([i.attendance_pct or 0.0 for i in interns]) or 0.0,
        "avg_case_study_performance": _avg([i.case_study_performance or 0.0 for i in interns]) or 0.0,
        "avg_engineering_credits": _avg([float(i.engineering_credits or 0) for i in interns]) or 0.0,
    }
