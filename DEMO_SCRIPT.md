# Live Demonstration Script

Organized around the grading rubric's seven criteria, in weight order, so a
live walkthrough hits every one by construction instead of touring the API
in an arbitrary order and hoping the criteria come up.

**Status of this script as written: drafted and code-verified, not yet
live-rehearsed.** Every command below is real — copied from this repo's own
routers/services — and every example response shown is reconstructed from
this repo's own passing test assertions (see "How the examples in this
script were produced" at the bottom), not fabricated. But the case study's
own Day 19 deliverable is "demo rehearsed once end-to-end" against a
*running* instance, and that has not happened yet: the authoring
environment used to draft this script has no Docker daemon and no route to
PyPI, so `docker compose up` / `pip install` cannot be executed here. **Run
the "Setup" section below for real on your machine before presenting**, and
update the example responses with whatever your run actually returns if
they differ (they should be close — team/skill assignment depends on
Faker's random seed and clustering, so exact names/scores will vary; the
shapes and score ranges will not).

## Setup (before anyone's watching)

```bash
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/generate_demo_dataset.py
curl -X POST http://localhost:8000/embeddings/generate-all
```

The curated dataset seeds skill text but not embeddings — the last command
generates them for every intern in one batch call. Do this *before* anyone's
watching: it downloads the sentence-transformers model weights on first
run, which takes a little while.

Confirm readiness before anyone's watching:
```bash
curl http://localhost:8000/health
# {"api":"ok","database":"ok"}
```

**Known gotcha to plan around (see DAY19_GUIDE.md):** `/recommend-teams`
reclusters the *entire* candidate pool by skill embedding — it will not
reproduce two specific hand-picked teams. For the Innovation section's
chemistry contrast below, create the two demo teams directly via
`POST /teams` + `POST /teams/{id}/members` using two deliberately
skill-different groups from the curated dataset, rather than trusting
`/recommend-teams` to land on them.

## 1. AI Architecture — 20%

**Say:** "Twelve AI engines, each its own FastAPI router and service
module, chained together — not one monolith."

**Show:** Swagger UI at `/docs` — scroll the tag list top to bottom. This
repo currently has 21 router modules and 18 service modules (including the
Engineering Knowledge Graph added in the post-Day-20 gap-fix pass — see
`app/services/knowledge_graph_service.py`); point out that every tag has
its own docstring-derived description, not generic auto-gen text.

**Then run the one call that chains everything:**

```bash
curl -X POST http://localhost:8000/recommend-teams \
  -H "Content-Type: application/json" \
  -d '{"team_size": 4, "algorithm": "kmeans"}'
```

Expected response shape (field names and score ranges are real — verified
against `tests/test_router_recommend_teams.py`; the actual names/IDs your
run returns will differ):

```json
{
  "algorithm": "kmeans",
  "teams": [
    {
      "id": 1,
      "members": [
        {"intern_id": 1, "full_name": "...", "role": "Lead", "skill_archetype": 3},
        {"intern_id": 2, "full_name": "...", "role": "Member", "skill_archetype": 2}
      ],
      "suggested_leader_intern_id": 1,
      "skill_matrix": {},
      "compatibility_score": 72.56,
      "success_probability": 82.32,
      "overall_score": 0,
      "risks": [],
      "project": null,
      "workload": [],
      "explanation": {
        "base_value": 0.0,
        "factors": [],
        "summary": "",
        "reasons": []
      }
    }
  ],
  "unassigned_intern_ids": []
}
```

**Say:** "One request just ran clustering, compatibility, project
matching, workload distribution, success prediction, risk analysis, and
explainability — that's the Day 10 Checkpoint 2 integration, and it's one
of the reasons Architecture and Team Matching Accuracy are graded
separately from each other even though this one call touches both."

**Then show the Engineering Knowledge Graph** — the architecture
requirement that was designed on Day 1 (NetworkX, in-process, specifically
to avoid a Neo4j server for a 4-week build) but not actually wired up
until a post-Day-20 QA pass caught the gap:

```bash
curl http://localhost:8000/knowledge-graph/summary
curl http://localhost:8000/knowledge-graph/skill/Laravel/interns
curl http://localhost:8000/knowledge-graph/intern/1/recommended-collaborators
```

**Say:** "The graph answers 'which Laravel developers should work
together' the same way a human mentor reasons about it — through shared
skills and shared history — and every recommendation carries the actual
evidence (shared skill names, past team outcome) it was scored from, not
an opaque number."

## 2. Team Matching Accuracy — 20%

**Say:** "Formation isn't random grouping — it's skill-embedding
clustering, and every team gets a measurable diversity/compatibility
score."

**Point at the same response:** `compatibility_score` on the first team —
explain this comes from Day 6's cosine-similarity matching feeding Day 7's
clustering, not a hand-tuned heuristic.

**Then answer the case study's own example question live** — "which
interns pair well" — via matching:

```bash
curl http://localhost:8000/matching/interns/1/recommendations
```

## 3. Business Value — 20%

**Say:** "This directly answers the coordinator questions the case study
poses — not paraphrased, the literal ones."

**Show the Mentor dashboard** (`http://localhost:8501`, Mentor view) — the
same `/recommend-teams` output rendered for a non-technical viewer, with
leader suggestions and project fit visible without touching curl.

**Then show the Student dashboard**, one intern's own view:

```bash
curl http://localhost:8000/student/1/dashboard
```

Expected shape (verified against `tests/test_router_student_dashboard.py`):

```json
{
  "intern_id": 1,
  "full_name": "...",
  "strengths": ["..."],
  "team": {
    "team_id": 1,
    "role": "Lead",
    "success_probability": 82.32,
    "project_title": "...",
    "teammates": ["...", "..."],
    "compatibility_score": 72.0,
    "suggested_responsibility": null
  }
}
```

**Say:** "That's the same intern flagged as a leadership candidate in the
recommend-teams call a minute ago, now seeing it from their own side."

## 4. Explainability — 15%

**Say:** "Every success-probability number ships with a reason attached —
computed by SHAP against the live model, not a canned explanation."

```bash
curl http://localhost:8000/success-probability/team/1
```

Expected shape (verified against `tests/test_router_success_probability.py`
— exactly 3 factors, each with a direction):

```json
{
  "team_id": 1,
  "success_probability": 82.32,
  "features": {"team_balance": 1.0, "avg_attendance_pct": 87.82, "avg_feedback_score": 6.85},
  "explanation": {
    "base_value": 0.462,
    "factors": [
      {"feature": "team_balance", "shap_value": 0.6563, "direction": "increased"},
      {"feature": "avg_feedback_score", "shap_value": 0.2501, "direction": "increased"},
      {"feature": "avg_attendance_pct", "shap_value": 0.1695, "direction": "increased"}
    ],
    "summary": "Team skill balance was the strongest positive driver behind this team's success probability.",
    "reasons": [
      "Team skill balance increased the predicted success probability.",
      "Average attendance increased the predicted success probability.",
      "Average mentor feedback increased the predicted success probability."
    ]
  }
}
```

**Say:** "That `reasons` list is what actually renders in the Mentor
dashboard — a coordinator never sees a bare score with no context."

## 5. Innovation — 5% (do this before Scalability — it's more visual)

**Say:** "Two bonus engines beyond the core spec: Automatic Team
Rebalancing and Team Chemistry Prediction, and I can show both changing
behavior on real data, not just returning a static field."

**Chemistry contrast — the centerpiece of this section.** Create two teams
directly by intern-ID range from the curated dataset (see the Setup
gotcha above): one with a single unmistakable leader, one with two
competing leaders.

```bash
curl http://localhost:8000/team-chemistry/team/{clean_leader_team_id}
curl http://localhost:8000/team-chemistry/team/{competing_leader_team_id}
```

Response shape is fixed and verified (`tests/test_router_team_chemistry.py`):
`chemistry_score` (0-100), a `label` of `"Strong"`/`"Workable"`/`"Fragile"`,
and a `components` object with exactly four keys — `leadership_balance`,
`shared_interests`, `communication_spread`, `feedback_sentiment` — each
carrying `raw_score`, `weight`, `contribution`. The test suite confirms
`leadership_balance.raw_score` measurably drops when a second high-leadership
member joins an existing team — that's the real, asserted behavior to
narrate live, not a canned number.

**Say:** "Same signal, same weighting, different real input — the flag
only fires when it's actually earned."

**Rebalancing, on a team with a genuinely unavailable member:**

```bash
curl http://localhost:8000/rebalance/needed
curl -X POST http://localhost:8000/rebalance/team/{id}
```

Mark a member `is_available: false` via `PUT /interns/{id}` first so
`/rebalance/needed` has something to list. The router swaps in the
closest-fitting available replacement by embedding distance and rescores
the team through the same success-probability/compatibility pipeline —
`tests/test_router_rebalance.py` asserts the swap picks the nearer
candidate over a farther one, and that leadership reassigns if the
departing member was the team's Lead.

## 6. Scalability — 10%

**Say:** "Async FastAPI, every engine a separately deployable/testable
module, containerized, with a documented caching path if load ever
justifies it."

**Show:** `docker-compose.yml` (independently-scaled services) and
`ARCHITECTURE.md`'s v4 layering diagram — point out that Services and
Repositories are separate layers specifically so an engine's business
logic never depends on how it's queried.

## 7. Documentation — 10%

**Say:** "Nothing here requires reading the source to understand."

**Show, don't just say:** open `README.md` (Features/Tech Stack/Quick
Start), `API_DOCUMENTATION.md`, `DATABASE_DESIGN.md`, and
`DEPLOYMENT_GUIDE.md` side by side for ten seconds each — the point is that
all four exist and are current, not a deep read of any one.

## Closing

**Say:** "This engine suite is backed by an automated test suite covering
every router, including the exact endpoints just called — this isn't
demoed once and hoped for; it's asserted on every change."

```bash
docker compose exec backend pytest tests/ -v
```

This repo currently has 39 test files and 233 `def test_...` functions
(counted directly from the `tests/` directory, including
`test_knowledge_graph_service.py` and `test_router_knowledge_graph.py`
added in the post-Day-20 gap-fix pass; the live number pytest reports may
differ slightly if any are parametrized). State whatever number your own
`pytest tests/ -v` run actually reports — don't read this count aloud as
if it's the live result.

## How the examples in this script were produced

This script was **not** drafted by guessing plausible-looking JSON. Every
example response above was reconstructed directly from this repo's own
test assertions — `tests/test_router_recommend_teams.py`,
`test_router_student_dashboard.py`, `test_router_success_probability.py`,
`test_router_team_chemistry.py`, and `test_router_rebalance.py` — which
assert the exact field names, value ranges, and structural invariants
shown (e.g. "exactly 3 factors," "exactly these 4 component keys,"
"`leadership_balance` drops when a second strong leader joins"). Those
tests are real, checked-in code; treat the shapes above as trustworthy.
The *specific numbers* (82.32, 0.6563, etc.) are illustrative placeholders
drawn from one hypothetical worked example, not values captured from a
live run — your dataset's random seed will produce different numbers in
the same ranges.

What has **not** happened yet, and needs to happen before this counts as
"rehearsed" per the Day 19 deliverable:

1. Actually run `docker compose up --build -d` and the seeding/embedding
   commands above on a machine with Docker and internet access.
2. Actually execute every `curl` command in this script against that
   running instance and confirm the real response matches these shapes.
3. Replace the illustrative numbers above with your real captured output
   (or leave them as shape-reference and read the live terminal output
   during the actual presentation instead — either is fine, but decide
   which before presenting so it isn't decided live).
4. Actually create the two chemistry-contrast teams by ID range (Setup
   gotcha) and confirm the leadership-conflict flag actually differs
   between them on your seeded data.
5. Actually run `pytest tests/ -v` and note the real pass count for the
   Closing section.

None of the above requires code changes — the engines, routers, and tests
already exist and are unchanged from Day 18. This is purely an execution
step that could not be completed inside the sandboxed authoring
environment (no Docker daemon, no PyPI/Hugging Face network access) and
needs a normal developer machine.
