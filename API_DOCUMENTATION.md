# API Documentation

Written Day 18. The full interactive reference is always Swagger UI at
`/docs` (or the raw OpenAPI schema at `/openapi.json`) once the stack is
running — this document is a narrated companion to that, organized by
engine rather than alphabetically, with the "why," the error cases worth
knowing about, and a couple of full request/response examples for the
endpoints a demo actually walks through. It intentionally doesn't restate
every field of every schema — `app/schemas.py` and `/docs` are the source
of truth for exact shapes.

## Base URL and auth

No authentication layer exists in this project (out of scope per the
original spec — see `ARCHITECTURE.md`/`README.md`). Locally:
`http://localhost:8000`. On a hosted demo, whatever URL
`DEPLOYMENT_GUIDE.md`'s hosted-demo section gives you.

## Route groups at a glance

22 route groups, grouped here by the day/engine that introduced them
(21 from Days 1-16, plus the Engineering Knowledge Graph added in the
post-Day-20 gap-fix pass — see that section below).

### Core CRUD (Days 1-3)

| Method | Path | Purpose |
|---|---|---|
| GET | `/interns` | List all interns |
| GET | `/interns/{id}` | Get one intern |
| POST | `/interns` | Create an intern |
| PUT | `/interns/{id}` | Update an intern (auto-regenerates its embedding if skill-relevant fields changed — best-effort, never fails the update) |
| DELETE | `/interns/{id}` | Delete an intern |
| GET/POST/PUT/DELETE | `/projects`, `/projects/{id}` | Same CRUD shape for projects |
| GET/POST/PUT/DELETE | `/teams`, `/teams/{id}` | Team CRUD |
| POST | `/teams/{id}/members` | Add a member to a team |
| DELETE | `/teams/{id}/members/{intern_id}` | Remove a member |
| POST | `/import` | Bulk CSV/JSON upsert of intern records (simulates a portal export) |

### Embeddings + Skill Matrix (Day 4)

| Method | Path | Purpose |
|---|---|---|
| POST | `/embeddings/interns/{id}/generate` | Force-regenerate one intern's embedding |
| POST | `/embeddings/generate-all` | Batch-generate for every intern missing one |
| GET | `/embeddings/interns/{id}` | Read one intern's embedding metadata (not the raw vector) |
| GET | `/embeddings/status` | Per-intern embedding freshness across the org |
| GET | `/skill-matrix/team/{team_id}` | Per-skill frequency/proficiency for one team |
| GET | `/skill-matrix/technology-frequency` | Org-wide tech-stack frequency |
| GET | `/skill-matrix/proficiency-aggregation` | Org-wide proficiency aggregation |

### Matching + Compatibility + Recommendations (Day 6)

| Method | Path | Purpose |
|---|---|---|
| GET | `/matching/interns/{id}/recommendations` | Most similar interns by embedding cosine similarity |
| GET | `/matching/interns/{id}/complementary` | *Least* similar (complementary-skill) interns |
| GET | `/matching/teams/{id}/diversity` | Team diversity score |
| GET | `/compatibility/pair?intern_a_id=&intern_b_id=` | Pairwise 6-signal compatibility score |
| GET | `/compatibility/team/{id}` | Team-level compatibility (persisted, cached on `Team.compatibility_score`) |
| POST | `/compatibility/team/{id}/recalculate` | Force a fresh compatibility computation and re-persist it |
| GET | `/recommendations/interns/{id}` | Blended similarity + compatibility teammate recommendations |

### Team Formation + Leadership (Day 7)

| Method | Path | Purpose |
|---|---|---|
| POST | `/team-formation/preview` | Cluster a candidate pool into balanced teams — returns candidates, doesn't persist |
| POST | `/team-formation/commit` | Same clustering, persists the resulting teams |
| GET | `/leadership/interns/{id}/score` | One intern's leadership score breakdown |
| GET | `/leadership/team/{id}/suggest` | Suggest (don't apply) a leader for a team |
| POST | `/leadership/team/{id}/apply` | Apply the suggested leader (sets `role="Lead"`) |

### Project Matching + Workload (Day 8)

| Method | Path | Purpose |
|---|---|---|
| GET | `/project-matching/team/{id}` | Rank candidate projects against a team's skills |
| POST | `/project-matching/team/{id}/assign` | Assign a project to a team |
| GET | `/workload/team/{id}` | Preview per-member responsibility assignment |
| POST | `/workload/team/{id}/apply` | Persist the workload assignment |

### Success Probability + Risk Analysis (Day 9)

| Method | Path | Purpose |
|---|---|---|
| GET | `/success-probability/team/{id}` | Trained-model prediction + Day 11 SHAP `explanation` |
| POST | `/success-probability/team/{id}/recalculate` | Force a fresh prediction and re-persist it |
| GET | `/risk-analysis/team/{id}` | Rule-based risk flags |
| POST | `/risk-analysis/team/{id}/recalculate` | Force a fresh risk analysis |

### Checkpoint 2 (Day 10)

| Method | Path | Purpose |
|---|---|---|
| POST | `/recommend-teams` | The single integration endpoint: clusters a pool, then runs compatibility, project matching, workload, success probability, risk, and (Day 11) explainability against every resulting team in one call |

### Dashboards (Days 13-14)

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin-analytics/teams` | Cross-team analytics rollup |
| GET | `/admin-analytics/projects` | Per-project success rates |
| GET | `/admin-analytics/resource-utilization` | Org-wide resource utilization |
| GET | `/student/{intern_id}/dashboard` | One intern's own team/role/score view |

### Bonus features (Day 16)

| Method | Path | Purpose |
|---|---|---|
| GET | `/rebalance/needed` | Teams with at least one unavailable member |
| POST | `/rebalance/team/{id}` | Find replacements, swap membership, re-suggest leader, rescore |
| GET | `/team-chemistry/team/{id}` | Team-level interpersonal-friction signal (4 weighted components) |

### Engineering Knowledge Graph (gap-fix, post-Day-20)

NetworkX in-process graph over interns/skills/teams/projects — see
`app/services/knowledge_graph_service.py` for the node/edge schema. Not
persisted; rebuilt from a DB query on every call.

| Method | Path | Purpose |
|---|---|---|
| GET | `/knowledge-graph/summary` | Node/edge counts by type — a quick view of what's actually connected right now |
| GET | `/knowledge-graph/skill/{skill_name}/interns` | Every intern with that skill, ranked by proficiency (e.g. `/knowledge-graph/skill/Laravel/interns` answers the case study's "which Laravel developers should work together?" at the candidate-finding step) |
| GET | `/knowledge-graph/intern/{intern_id}/recommended-collaborators?limit=` | Graph-native collaborator ranking (shared skills + past WORKED_WITH history), each result carrying its evidence, not just a score |
| GET | `/knowledge-graph/path?intern_a_id=&intern_b_id=` | Shortest explainable path connecting two interns (shared skill, shared team, or direct past collaboration); `found: false` if they're in disconnected parts of the graph |

## Common error shapes

Every engine follows the same convention, tightened during Day 12's API
Finalization pass:

- **`404`** — the referenced entity (intern/team/project) doesn't exist.
- **`409`** — the entity exists but the requested operation doesn't make
  sense against its current state (e.g. `POST /rebalance/team/{id}`
  against a team with no unavailable members; `GET /workload/team/{id}`
  against a team with no members; `GET /embeddings/interns/{id}` before
  one's ever been generated). Chosen over `404` specifically so a client
  can tell "doesn't exist" apart from "exists but not ready yet."
- **`422`** — request validation failure (FastAPI/Pydantic default),
  e.g. an out-of-range `difficulty_level` that isn't one of the
  `Literal` values Day 12 tightened `schemas.py` to.

## Two end-to-end example flows

### 1. Form a team and see every engine's output in one call

```bash
curl -X POST http://localhost:8000/recommend-teams \
  -H "Content-Type: application/json" \
  -d '{"team_size": 4, "algorithm": "kmeans"}'
```

`intern_ids` can be added to the body to use a specific candidate pool;
omitted (as above), it defaults to available, unassigned interns that
already have an embedding.

Response shape (abbreviated — see `schemas.RecommendTeamsResultOut` for
the full model):

```json
{
  "algorithm": "kmeans",
  "archetype_count": 2,
  "unassigned_intern_ids": [],
  "teams": [
    {
      "id": 1, "name": "Team Alpha",
      "members": [ { "intern_id": 12, "full_name": "...", "role": "Lead", "skill_archetype": 0 } ],
      "suggested_leader_intern_id": 12,
      "diversity_score": 0.64,
      "compatibility_score": 78.4,
      "project": { "project_id": 3, "match_score": 0.82 },
      "workload": [ { "intern_id": 12, "suggested_responsibility": "Backend API" } ],
      "success_probability": 0.71,
      "risks": [],
      "overall_score": 0.76,
      "explanation": { "team_balance": {"contribution": 0.24}, "avg_attendance_pct": {"contribution": 0.18} }
    }
  ]
}
```

`explanation` is the Day 11 SHAP breakdown of the *same*
`success_probability` value the team object carries — same reasoning
`ARCHITECTURE.md`'s Day 11 section gives: it explains the live engine
output, not a separately-computed number.

### 2. Demo the two Day 16 bonus features against an existing team

```bash
# 1. See which teams currently have an unavailable member
curl http://localhost:8000/rebalance/needed

# 2. Swap that member out for the best-fit available replacement,
#    re-suggest a leader if needed, and rescore
curl -X POST http://localhost:8000/rebalance/team/1

# 3. Pull the team-level chemistry signal for the same team
curl http://localhost:8000/team-chemistry/team/1
```

`scripts/generate_demo_dataset.py` (Day 18) seeds two interns as
unavailable up front specifically so step 1 has something to show
immediately after `/recommend-teams` runs, without a manual
`PUT /interns/{id}` step first — see that script's docstring for the
full curated-dataset design.

## Where to look next

- **Exact request/response schemas:** `/docs` (Swagger) or
  `app/schemas.py`.
- **Why each engine is shaped the way it is:** the per-day
  `DAY*_GUIDE.md` files, and `ARCHITECTURE.md` for the cross-cutting
  layering decisions.
- **Database columns each endpoint reads/writes:** `DATABASE_DESIGN.md`.
- **Running this locally or hosted:** `DEPLOYMENT_GUIDE.md`.
