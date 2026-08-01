"""
Day 8 — Project Recommendation Engine.

Matches a team's **combined** skill set — union across every member, same
aggregation style as Day 6's team diversity score — against each project's
required_tech_stack. The score is coverage: what fraction of what the
project needs, the team can deliver.

Why coverage is `matched / required`, not a symmetric similarity like
Jaccard: the question a mentor actually asks is "can this team deliver what
the project needs", not "how similar are these two skill sets" overall. A
team with *many* extra skills beyond what a small project needs should
still score 1.0 if it covers every requirement — Jaccard would incorrectly
penalize that team for having a broader skill set than the project calls
for.
"""
from app import models
from app.services.skill_utils import intern_skill_names


def _parse_stack(text: str | None) -> list[str]:
    return [token.strip() for token in (text or "").split(",") if token.strip()]


def team_skill_set(members: list[models.Intern]) -> set[str]:
    """Union of every member's skill/technology names — same aggregation
    style Day 6's team_diversity uses, just unioned instead of compared."""
    skills: set[str] = set()
    for member in members:
        skills |= intern_skill_names(member)
    return skills


def score_project_fit(team_skills: set[str], project: models.Project) -> dict:
    """Coverage score (0.0-1.0) of a team's combined skills against one
    project's required_tech_stack, plus the matched/missing/extra
    breakdown that makes the score explainable."""
    required = _parse_stack(project.required_tech_stack)
    required_lower = {r.lower() for r in required}
    team_lower = {s.lower() for s in team_skills}

    matched = [r for r in required if r.lower() in team_lower]
    missing = [r for r in required if r.lower() not in team_lower]
    extra = sorted(s for s in team_skills if s.lower() not in required_lower)

    coverage = (len(matched) / len(required)) if required else 0.0

    return {
        "project_id": project.id,
        "title": project.title,
        "difficulty_level": project.difficulty_level,
        "coverage_score": round(coverage, 4),
        "matched_skills": matched,
        "missing_skills": missing,
        "extra_skills": extra,
        "required_skill_count": len(required),
    }


def recommend_projects(members: list[models.Intern], projects: list[models.Project]) -> list[dict]:
    """Every project scored against the team's combined skill set, ranked
    by coverage descending (ties broken by project id for determinism)."""
    skills = team_skill_set(members)
    scored = [score_project_fit(skills, project) for project in projects]
    scored.sort(key=lambda r: (-r["coverage_score"], r["project_id"]))
    return scored
