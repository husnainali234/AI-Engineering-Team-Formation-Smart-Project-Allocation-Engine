# Day 8 — Project Recommendation + Workload: Full Walkthrough

Goal for today: **every formed team gets a recommended project plus a
per-member workload breakdown.** Built directly on top of Day 7's teams
(and Day 1's `Project`/`TeamMember.suggested_responsibility` fields, which
have been sitting ready for exactly this since the original ERD) — no
schema changes today.

---

## What's new since Day 7

```
ezitech-ai020/
├── app/
│   ├── services/
│   │   ├── project_recommendation_service.py   # NEW — team-vs-project coverage scoring
│   │   └── workload_service.py                 # NEW — per-member responsibility assignment
│   ├── repositories/
│   │   ├── project_repository.py               # NEW — list_all()/get_by_id() for Project
│   │   └── team_repository.py                  # UPDATED — get_by_id_with_members_and_interns()
│   ├── schemas.py                               # UPDATED — project-fit/workload schemas
│   ├── main.py                                  # UPDATED — wires in 2 new routers
│   └── routers/
│       ├── project_matching.py                  # NEW — /project-matching/*
│       └── workload.py                          # NEW — /workload/*
└── tests/
    ├── test_project_recommendation_service.py   # NEW
    ├── test_workload_service.py                 # NEW
    └── test_router_project_matching_and_workload.py  # NEW
```

## 1. Project Recommendation Engine

Matches a team's **combined** skill set — union across every member, same
aggregation style as Day 6's team diversity score — against each project's
`required_tech_stack`. The score is coverage: what fraction of what the
project needs, the team can deliver.

```bash
curl http://localhost:8000/project-matching/team/5
```

```json
{
  "team_id": 5,
  "team_name": "Auto-Formed Team 1",
  "team_skill_count": 9,
  "recommendations": [
    {
      "project_id": 2, "title": "Laravel Inventory System", "difficulty_level": "Medium",
      "coverage_score": 1.0, "matched_skills": ["Laravel", "MySQL", "Vue"],
      "missing_skills": [], "extra_skills": ["Docker", "Git"], "required_skill_count": 3
    },
    {
      "project_id": 4, "title": "ML Recommendation API", "difficulty_level": "Hard",
      "coverage_score": 0.33, "matched_skills": ["Python"],
      "missing_skills": ["TensorFlow", "FastAPI"], "extra_skills": [...], "required_skill_count": 3
    }
  ]
}
```

This is the mechanism behind the case study's own worked examples: "which
Laravel devs pair" falls out naturally when a team's combined skills score
`1.0` coverage against a Laravel project. "AI engineer folded into a MERN
project" works the same way — coverage is computed against the *team's*
blended profile, not any single member's, so one member's AI/ML specialty
doesn't need to individually match a MERN requirement as long as the team's
combined React/Node/Mongo coverage is strong. See the module docstring in
`project_recommendation_service.py` for the full reasoning.

Read-only, like Day 6/7's `GET .../suggest` endpoints — nothing is written
until you explicitly assign:

```bash
curl -X POST "http://localhost:8000/project-matching/team/5/assign"
# or pin a specific project instead of auto-picking the top recommendation:
curl -X POST "http://localhost:8000/project-matching/team/5/assign?project_id=2"
```

Persists to `Team.project_id` — the field Day 1's ERD already reserved for
this.

## 2. Workload Distribution

Once a team has a project, each required skill gets assigned to whichever
member is best positioned to own it — highest structured proficiency first,
then whoever's carrying the fewest assignments so far (so work spreads out
instead of piling onto one strong generalist):

```bash
curl http://localhost:8000/workload/team/5
```

```json
{
  "team_id": 5, "team_name": "Auto-Formed Team 1",
  "project_id": 2, "project_title": "Laravel Inventory System",
  "assignments": [
    {"intern_id": 3, "full_name": "...", "role": "Lead",
     "assigned_skills": ["Laravel"], "suggested_responsibility": "Own Laravel implementation."},
    {"intern_id": 7, "full_name": "...", "role": "Member",
     "assigned_skills": ["MySQL", "Vue"], "suggested_responsibility": "Own MySQL, Vue implementation."}
  ]
}
```

A required skill nobody on the team lists doesn't go unassigned — it goes
to whoever's both the most generalist (broadest overall skill set — likely
to ramp up fastest) and least loaded so far. A member left with no assigned
skill at all still gets a concrete responsibility: the team's `Lead` gets
coordination/code-review framing, everyone else gets a general
support/testing framing — nobody's workload breakdown is blank.

Read-only preview by default; `404` if the team has no members, `409` if it
has no project assigned yet (workload only makes sense once you know what
the team is building):

```bash
curl -X POST http://localhost:8000/workload/team/5/apply
```

Persists each entry's `suggested_responsibility` onto its `TeamMember` row
— the field the original Day 1 ERD reserved for exactly this.

## 3. Run the test suite

```bash
docker compose exec backend pytest tests/ -v
```

`test_project_recommendation_service.py` covers coverage scoring directly
(full/partial/zero coverage, case-insensitive matching, ranking order).
`test_workload_service.py` covers assignment logic (proficiency-based
matching, the generalist fallback for unmatched skills, the Lead/Member
fallback responsibilities, deterministic Lead-first ordering).
`test_router_project_matching_and_workload.py` integration-tests both
routers' HTTP layer, including the 404/409 paths.

## 4. Commit

```bash
git add .
git commit -m "Day 8: Project Recommendation Engine (skill coverage) and Workload Distribution"
git push
```

## Design notes worth knowing

- **Why coverage is `matched / required`, not a symmetric similarity like
  Jaccard**: the question a mentor actually asks is "can this team deliver
  what the project needs", not "how similar are these two skill sets"
  overall. A team with *many* extra skills beyond what a small project
  needs should still score `1.0` if it covers every requirement — Jaccard
  would incorrectly penalize that team for having a broader skill set than
  the project calls for.
- **Why workload assignment is greedy per-skill, not a global
  optimization**: same explainability reasoning as Day 7's round-robin —
  "highest proficiency, then least-loaded" is one sentence to explain to a
  mentor and fully deterministic, versus a combinatorial assignment
  optimizer that would need its own justification for the Explainability
  criterion.
- **Why an unmatched required skill goes to the generalist, not simply the
  least-loaded member**: least-loaded alone could hand a totally unfamiliar
  skill to someone who's a narrow specialist in something unrelated.
  Breadth of existing skills is a better (if imperfect) proxy for "who can
  ramp up on this fastest" than pure workload balance alone.
- **Why `/project-matching` and `/workload` are separate routers instead of
  one combined endpoint**: same "each engine independently useful and
  independently testable" principle Day 6 established — a mentor might want
  project recommendations without recomputing workload, or want to re-run
  workload after changing which project a team is assigned to without
  touching the recommendation logic at all.

## End-of-Day 8 Checklist

- [ ] `GET /project-matching/team/{id}` returns projects ranked by skill
      coverage against the team's combined skill set
- [ ] `POST /project-matching/team/{id}/assign` persists to
      `Team.project_id`, with or without an explicit `project_id`
- [ ] `GET /workload/team/{id}` returns a per-member responsibility
      breakdown once a project is assigned, `409` before that
- [ ] `POST /workload/team/{id}/apply` persists
      `TeamMember.suggested_responsibility` for every member
- [ ] `pytest tests/` (full Day 1-8 suite) passes
- [ ] Everything committed and pushed

If all boxes are checked, every formed team now gets a recommended project
plus a per-member workload breakdown — today's deliverable — and Week 2
closes out with Day 9's Success Probability + Risk Analysis reading
straight off of this: team balance (Day 7), compatibility (Day 6),
attendance/feedback (Days 1-2), and now project fit (today).
