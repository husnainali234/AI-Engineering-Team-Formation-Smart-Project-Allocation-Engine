"""
Day 4 — Skill Matrix generation.

Three related-but-distinct views over the same underlying data, matching the
Day 4 spec's three bullet points:

    - technology_frequency: how many interns (in scope) know each
      skill/technology at all — a simple headcount, no proficiency involved.
    - proficiency_aggregation: for skills with structured InternSkill rows,
      the avg/min/max proficiency (1-5) among interns who have that skill.
    - team_skill_matrix: the two combined into one per-skill table, scoped
      to a single team — the actual "Skill Matrix" a team lead would look at.

See app/services/skill_utils.py for why both InternSkill rows and the
free-text technology_stack field are treated as skill sources.
"""
from collections import defaultdict

from app import models
from app.services.skill_utils import intern_proficiency_map, intern_skill_names


def technology_frequency(interns: list[models.Intern]) -> dict[str, int]:
    """skill/technology name -> number of interns (in the given scope) who
    have it, sorted most-common first."""
    counts: dict[str, int] = defaultdict(int)
    for intern in interns:
        for name in intern_skill_names(intern):
            counts[name] += 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def proficiency_aggregation(interns: list[models.Intern]) -> dict[str, dict[str, float]]:
    """skill name -> {avg_proficiency, min_proficiency, max_proficiency,
    intern_count}, computed only from structured InternSkill rows (proficiency
    has no meaning for a technology_stack-only mention)."""
    levels: dict[str, list[int]] = defaultdict(list)
    for intern in interns:
        for name, proficiency in intern_proficiency_map(intern).items():
            levels[name].append(proficiency)

    return {
        name: {
            "avg_proficiency": round(sum(values) / len(values), 2),
            "min_proficiency": min(values),
            "max_proficiency": max(values),
            "rated_intern_count": len(values),
        }
        for name, values in levels.items()
    }


def build_skill_matrix(interns: list[models.Intern]) -> list[dict]:
    """The combined per-skill table: frequency + proficiency stats +
    which interns contribute it. This is what GET /skill-matrix/team/{id}
    returns."""
    freq = technology_frequency(interns)
    prof = proficiency_aggregation(interns)

    holders: dict[str, list[dict]] = defaultdict(list)
    for intern in interns:
        proficiencies = intern_proficiency_map(intern)
        for name in intern_skill_names(intern):
            holders[name].append({
                "intern_id": intern.id,
                "full_name": intern.full_name,
                "proficiency": proficiencies.get(name),  # None if from technology_stack only
            })

    rows = []
    for name, count in freq.items():
        row = {
            "skill_name": name,
            "intern_count": count,
            "interns": holders[name],
        }
        row.update(prof.get(name, {"avg_proficiency": None, "min_proficiency": None, "max_proficiency": None}))
        rows.append(row)

    # Most-common skills first, consistent with technology_frequency's ordering.
    rows.sort(key=lambda r: r["intern_count"], reverse=True)
    return rows
