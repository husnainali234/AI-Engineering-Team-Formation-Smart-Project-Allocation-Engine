"""
Day 14 — Student Dashboard: assigned team, role, compatibility score,
strengths, responsibilities.

Rule-based, not ML — same explainability-first reasoning as Day 7's
Leadership Detection and Day 9's Risk Analysis: a student reading their
own dashboard needs each callout tied to a real number, not a vague
compliment with no reasoning behind it.

Nothing here recomputes what other engines already decided.
compatibility_score/success_probability are read straight off the Team
row (whatever the last Day 6/Day 9/`recommend-teams` run wrote);
suggested_responsibility is read straight off the TeamMember row
(populated by Day 8's POST /workload/team/{id}/apply — None until that's
been run, which this module treats as "not assigned yet", not an error).

Day 15 checkpoint fix: Team.success_probability is persisted 0-1 (see
app/models.py), but every API response in this system — including this
one — reports success probability 0-100, same convention as
compatibility_score. build_team_view() now rescales on read instead of
passing the raw column value through (see
admin_analytics_service.SUCCESS_PROBABILITY_DB_TO_PCT for the same fix
applied to the Admin Dashboard's rollups).
"""
from app import models
from app.services.admin_analytics_service import SUCCESS_PROBABILITY_DB_TO_PCT
from app.services.skill_utils import intern_proficiency_map

STRONG_LEADERSHIP_THRESHOLD = 7.0
STRONG_COMMUNICATION_THRESHOLD = 7.0
STRONG_CASE_STUDY_THRESHOLD = 80.0
STRONG_ATTENDANCE_THRESHOLD = 95.0
# Deliberately higher than leadership_service's own GitHub saturation point
# (50, where the *leadership* component maxes out) — a "strength" callout
# is meant to be a genuine highlight, not just "cleared the leadership
# model's floor for full credit".
STRONG_GITHUB_ACTIVITY_THRESHOLD = 30
STRONG_SKILL_PROFICIENCY = 4
TOP_SKILL_COUNT = 3


def top_skills(intern: models.Intern) -> list[dict]:
    """Up to TOP_SKILL_COUNT skills at/above STRONG_SKILL_PROFICIENCY,
    highest proficiency first. Only structured InternSkill rows carry a
    proficiency rating — technology_stack-only entries (the only signal
    /import populates) have nothing to rank them by, so they're excluded
    here rather than assigned a fake proficiency."""
    proficiencies = intern_proficiency_map(intern)
    ranked = sorted(
        ((name, level) for name, level in proficiencies.items() if level >= STRONG_SKILL_PROFICIENCY),
        key=lambda item: item[1],
        reverse=True,
    )
    return [{"skill_name": name, "proficiency": level} for name, level in ranked[:TOP_SKILL_COUNT]]


def identify_strengths(intern: models.Intern) -> list[str]:
    """Plain-language strength callouts, one per signal that clears its
    threshold. Order mirrors the fields on the Intern model itself
    (leadership -> communication -> case study -> attendance -> GitHub),
    then top skills last."""
    strengths: list[str] = []

    if (intern.leadership_score or 0.0) >= STRONG_LEADERSHIP_THRESHOLD:
        strengths.append(f"Strong leadership signal ({intern.leadership_score:.1f}/10)")
    if (intern.communication_score or 0.0) >= STRONG_COMMUNICATION_THRESHOLD:
        strengths.append(f"Strong communicator ({intern.communication_score:.1f}/10)")
    if (intern.case_study_performance or 0.0) >= STRONG_CASE_STUDY_THRESHOLD:
        strengths.append(f"High case-study performance ({intern.case_study_performance:.0f})")
    if (intern.attendance_pct or 0.0) >= STRONG_ATTENDANCE_THRESHOLD:
        strengths.append(f"Excellent attendance ({intern.attendance_pct:.0f}%)")
    if (intern.github_contributions or 0) >= STRONG_GITHUB_ACTIVITY_THRESHOLD:
        strengths.append(f"Active GitHub contributor ({intern.github_contributions} contributions)")

    for skill in top_skills(intern):
        strengths.append(f"Skilled in {skill['skill_name']} ({skill['proficiency']}/5)")

    return strengths


def build_team_view(team_member: models.TeamMember) -> dict:
    """The team-scoped half of the dashboard: role, the team's persisted
    scores, project (if matched), workload responsibility (if assigned),
    and teammate names."""
    team = team_member.team
    teammates = sorted(
        m.intern.full_name
        for m in team.members
        if m.intern_id != team_member.intern_id and m.intern is not None
    )
    return {
        "team_id": team.id,
        "team_name": team.name,
        "role": team_member.role,
        "compatibility_score": team.compatibility_score or 0.0,
        "success_probability": (team.success_probability or 0.0) * SUCCESS_PROBABILITY_DB_TO_PCT,
        "project_title": team.project.title if team.project else None,
        "suggested_responsibility": team_member.suggested_responsibility,
        "teammates": teammates,
    }
