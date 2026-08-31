"""
Shared helpers for turning an Intern's skill data into a normalized set of
skill names — used by the Day 4 Skill Matrix, Day 6 Matching, and Day 6
Compatibility services alike, so all three agree on "what skills does this
intern have" instead of each reimplementing it slightly differently.

Two sources feed this, because the two entry points into the system
populate different fields:
    - `InternSkill` rows (structured, with a 1-5 proficiency) — populated by
      scripts/generate_mock_data.py and any client that calls the
      /interns/{id} skill-assignment flow directly against the DB.
    - `Intern.technology_stack` (free-text, comma-separated) — the only
      skill signal the Day 3 /import endpoint actually populates today.

Treating only InternSkill as "the" skill source would make the Skill
Matrix/Matching engines return near-empty results for anything that came in
through /import, which fails the Day 5 checkpoint ("Skill Matrix returns
correct values" after Import -> DB -> Embedding -> Skill Matrix). So both
sources are unioned per intern; technology_stack entries just don't carry a
proficiency rating.
"""
from app import models


def intern_skill_names(intern: models.Intern) -> set[str]:
    """Normalized (title-cased, deduped) set of every skill/technology name
    associated with this intern, from InternSkill rows and technology_stack."""
    names: set[str] = set()

    for intern_skill in intern.skills or []:
        if intern_skill.skill and intern_skill.skill.name:
            names.add(intern_skill.skill.name.strip())

    for token in (intern.technology_stack or "").split(","):
        token = token.strip()
        if token:
            names.add(token)

    return names


def intern_proficiency_map(intern: models.Intern) -> dict[str, int]:
    """skill name -> proficiency (1-5), from structured InternSkill rows
    only (technology_stack tokens carry no proficiency signal)."""
    return {
        intern_skill.skill.name.strip(): intern_skill.proficiency
        for intern_skill in (intern.skills or [])
        if intern_skill.skill and intern_skill.skill.name
    }


def skill_diversity_score(skills_a: set[str], skills_b: set[str]) -> float:
    """0.0-1.0: how little two skill sets overlap, i.e. how "complementary"
    they are. 1.0 = completely disjoint skill sets (maximally complementary),
    0.5 = identical skill sets (fully redundant), 0.0 = both sets empty
    (no signal either way).

    Formula: |union| / (|A| + |B|). For disjoint sets this is
    (|A|+|B|)/(|A|+|B|) = 1.0. For identical non-empty sets it's
    |A|/(2|A|) = 0.5. This intentionally differs from Jaccard
    (|intersection|/|union|), which would score identical sets as 1.0 —
    the opposite of what "diversity" should mean here.
    """
    total = len(skills_a) + len(skills_b)
    if total == 0:
        return 0.0
    union = skills_a | skills_b
    return len(union) / total


def group_diversity_score(skill_sets: list[set[str]]) -> float:
    """N-way generalization of skill_diversity_score, for a whole team
    rather than a pair: |union of all members' skills| / (sum of each
    member's skill-set size)."""
    total = sum(len(s) for s in skill_sets)
    if total == 0:
        return 0.0
    union: set[str] = set()
    for s in skill_sets:
        union |= s
    return len(union) / total
