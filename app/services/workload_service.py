"""
Day 8 — Workload Distribution.

Once a team has a project, each required skill gets assigned to whichever
member is best positioned to own it — highest structured proficiency
first, then whoever's carrying the fewest assignments so far (so work
spreads out instead of piling onto one strong generalist).

Why this is greedy per-skill, not a global optimization: same
explainability reasoning as Day 7's round-robin — "highest proficiency,
then least-loaded" is one sentence to explain to a mentor and fully
deterministic, versus a combinatorial assignment optimizer that would need
its own justification for the Explainability criterion.

Why an unmatched required skill goes to the generalist, not simply the
least-loaded member: least-loaded alone could hand a totally unfamiliar
skill to someone who's a narrow specialist in something unrelated. Breadth
of existing skills is a better (if imperfect) proxy for "who can ramp up on
this fastest" than pure workload balance alone.
"""
from app import models
from app.services.skill_utils import intern_proficiency_map, intern_skill_names

LEAD_FALLBACK_RESPONSIBILITY = "Coordinate the team and review teammates' work."
MEMBER_FALLBACK_RESPONSIBILITY = "Support the team with general implementation and testing."


def _parse_stack(text: str | None) -> list[str]:
    return [token.strip() for token in (text or "").split(",") if token.strip()]


def required_skill_count(project: models.Project) -> int:
    return len(_parse_stack(project.required_tech_stack))


def _proficiency_for(intern: models.Intern, skill_name: str) -> int:
    lower_map = {name.lower(): prof for name, prof in intern_proficiency_map(intern).items()}
    return lower_map.get(skill_name.lower(), 0)


def distribute_workload(team_members: list[models.TeamMember], project: models.Project) -> list[dict]:
    """Per-member responsibility breakdown for a team's assigned project.
    Returns rows ordered Lead-first, each with assigned_skills and a
    concrete suggested_responsibility (never blank)."""
    required = _parse_stack(project.required_tech_stack)

    # Lead-first, stable otherwise — deterministic regardless of DB row order.
    ordered_members = sorted(team_members, key=lambda tm: 0 if tm.role == "Lead" else 1)

    member_skill_sets = {tm.intern_id: intern_skill_names(tm.intern) for tm in ordered_members}
    assigned_skills: dict[int, list[str]] = {tm.intern_id: [] for tm in ordered_members}
    load_count: dict[int, int] = {tm.intern_id: 0 for tm in ordered_members}

    for skill in required:
        skill_lower = skill.lower()
        candidates = [
            tm
            for tm in ordered_members
            if skill_lower in {s.lower() for s in member_skill_sets[tm.intern_id]}
        ]

        if candidates:
            chosen = min(
                candidates,
                key=lambda tm: (
                    -_proficiency_for(tm.intern, skill),
                    load_count[tm.intern_id],
                    tm.intern_id,
                ),
            )
        else:
            # Nobody on the team lists this skill — hand it to the
            # broadest generalist (most distinct skills overall), least
            # loaded so far, as the best proxy for "who ramps up fastest".
            chosen = min(
                ordered_members,
                key=lambda tm: (
                    -len(member_skill_sets[tm.intern_id]),
                    load_count[tm.intern_id],
                    tm.intern_id,
                ),
            )

        assigned_skills[chosen.intern_id].append(skill)
        load_count[chosen.intern_id] += 1

    rows = []
    for tm in ordered_members:
        skills = assigned_skills[tm.intern_id]
        if skills:
            responsibility = f"Own {', '.join(skills)} implementation."
        elif tm.role == "Lead":
            responsibility = LEAD_FALLBACK_RESPONSIBILITY
        else:
            responsibility = MEMBER_FALLBACK_RESPONSIBILITY

        rows.append(
            {
                "intern_id": tm.intern_id,
                "full_name": tm.intern.full_name,
                "role": tm.role,
                "assigned_skills": skills,
                "suggested_responsibility": responsibility,
            }
        )

    return rows
