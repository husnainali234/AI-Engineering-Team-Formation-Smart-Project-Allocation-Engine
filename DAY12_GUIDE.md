# Day 12 — API Finalization + Mentor Dashboard

## Goal

Two parallel tracks per the execution guide: harden and document every
Recommendation API (Engineer A), and build the first real dashboard page —
Mentor — on top of Day 11's Streamlit scaffold (Engineer B).

## Track A — API Finalization

An audit pass over all 17 route groups, looking specifically for the three
things the guide calls out: OpenAPI schema completeness, consistent error
handling, and response contracts matching what's declared.

### Status code fixes

Two endpoints were returning `404` for a state that's really "the resource
exists, it's just not ready yet" — which every other engine in this
codebase treats as `409`:

| Endpoint | Was | Now | Why |
|---|---|---|---|
| `GET/POST /workload/team/{id}...` — team has no members | 404 | 409 | Matches `leadership`, `project-matching`, `risk-analysis`, `success-probability`, which all use 409 for "team exists but has no members" |
| `GET /embeddings/interns/{id}` — no embedding yet | 404 | 409 | Matches `matching.py`'s `EmbeddingMissingError` → 409 handling for the identical "intern exists, missing embedding" case |

Both were genuine inconsistencies, not stylistic nitpicks — a client
handling `/workload` or `/embeddings` errors would have needed different
logic than every other endpoint in the API for what's conceptually the
same situation. `tests/test_router_embeddings.py`'s
`test_get_embedding_404_before_generation` was renamed and updated to
`test_get_embedding_409_before_generation` accordingly.

### Schema tightening

Several `schemas.py` fields were a bare `str` with a comment listing the
actual allowed values (`# "kmeans" | "agglomerative"`) — turned into real
`Literal[...]` types so Swagger shows a dropdown instead of a free-text
box, and FastAPI validates the value itself instead of relying on each
service to raise its own `ValueError`:

- `algorithm`: `Literal["kmeans", "agglomerative"]`
- `difficulty_level`: `Literal["Easy", "Medium", "Hard"]`
- `role` (on algorithmically-generated output only — `FormedTeamMemberOut`):
  `Literal["Lead", "Member"]`
- `source_format`: `Literal["csv", "json"]`
- `direction` (explanation factors): `Literal["increased", "decreased", "neutral"]`
- `severity`: `Literal["low", "medium", "high"]`

Deliberately left as plain `str`: `TeamMemberBase.role` and
`WorkloadAssignmentOut.role`, since both mirror `TeamMember.role`, which
the general-purpose `POST /teams/{id}/members` CRUD endpoint allows to be
a freeform label — constraining those to `Literal["Lead", "Member"]` would
have silently broken a legitimate use case (a mentor manually labeling a
custom role) that the algorithmic engines never exercise.

Also added `Field(...)` descriptions to `TeamFormationRequest` and a
`ge=1` constraint on `team_size` — turns a request with `team_size=0`
into a clean 422 instead of a confusing runtime result.

### Swagger / documentation

- `app/main.py` now passes `openapi_tags` — a real one-line description
  for every one of the 17 route groups, so `/docs` reads as documentation
  rather than a bare endpoint list.
- Expanded the top-level app description to name all six engines plus the
  Explainable AI Layer.
- Added docstrings to the most important previously-undocumented
  endpoints: `POST /recommend-teams` (the integration endpoint itself),
  leadership score, compatibility pair, embeddings generate/get,
  skill-matrix frequency/aggregation, team diversity.
- Version bumped to `0.12.0` (also corrects a missed bump — Day 11 shipped
  under `0.8.0` by oversight).

All 156 existing tests still pass after every change in this track.

## Track B — Mentor Dashboard

`dashboard/pages/1_🧑‍🏫_Mentor_Dashboard.py` replaces the Day 11 skeleton
with the real thing, per the execution guide's four bullet points:

1. **Recommended Teams** — a form to pick a candidate pool (or leave it
   empty for the default available/unassigned pool), team size, and
   algorithm; submits to `POST /recommend-teams` and renders each team in
   its own expandable section: members, suggested leader, roles.
2. **Team Balance Analysis** — the team's skill matrix as a bar chart
   (`intern_count` per skill), plus the numeric diversity score.
3. **Collaboration Score** — the team's average compatibility score, plus
   a supplementary call to Day 6's `GET /compatibility/team/{id}` for the
   full pairwise breakdown (intentionally not inlined in
   `/recommend-teams`, which only carries the team average — inlining
   O(n²) pairs per team into every `/recommend-teams` response would bloat
   it for a value most callers don't need). The weakest pair is called out
   explicitly.
4. **Suggested Changes** — Day 9's risk flags (color-coded by severity)
   plus Day 11's SHAP-based explanation reasons, surfaced as an
   actionable "why" via a popover rather than requiring the mentor to
   separately query `/success-probability`.

Project fit and per-member workload assignments (Day 8) are also rendered
when a project was matched, since a mentor reviewing a recommended team
needs that context too, even though it's not one of the four bullet
points named explicitly.

### Implementation notes

- `dashboard/lib/api_client.py` gained a `post_json` helper alongside the
  existing `get_json` (Day 11 only ever needed GET calls) — with a longer
  default timeout, since `/recommend-teams` runs clustering plus six
  engines per team and can take noticeably longer than a plain lookup.
- `dashboard/requirements.txt` gained `pandas`, used for the tables and
  bar charts.
- Kept using Streamlit's own session state (`st.session_state`) to persist
  the last `/recommend-teams` result across reruns, so expanding one
  team's section doesn't lose the others' data or require re-submitting
  the form.

### Verification

Rather than just reading the code back, this was checked end-to-end:

1. Booted the real FastAPI backend against a throwaway SQLite database
   (`DATABASE_URL` override — the app already supports this since Day 1;
   confirmed no Postgres-specific column types are in use).
2. Monkeypatched the embedding model the same way `tests/conftest.py`'s
   `fake_embedding_model` fixture does, so `/recommend-teams` can actually
   run without downloading the real ~80MB sentence-transformers model.
3. Seeded real interns and a project via HTTP, then called
   `/recommend-teams` and `/compatibility/team/{id}` directly to confirm
   the response shapes match exactly what the dashboard code reads
   (`team["members"]`, `team["skill_matrix"]`, `team["project"]`,
   `team["workload"]`, `team["explanation"]`, pairwise `intern_a_id` /
   `intern_b_id` / `total_score`).
4. Used Streamlit's `AppTest` framework to execute the Mentor Dashboard
   page in-process against that live backend — filled in the form
   (selected all candidate interns, set team size and algorithm) and
   submitted it programmatically, the same as a person clicking through
   the UI would.

Result: zero exceptions on both the initial page load and after form
submission, with the expected team expander rendering with all 14
content blocks (members table, balance analysis, collaboration score,
project fit, workload, suggested changes, explanation) inside it.

## Running everything

```bash
docker compose exec backend pytest tests/ -v
```

156 tests pass across Days 1-12. The Mentor Dashboard has no new pytest
suite of its own (Streamlit pages aren't part of the backend's test
collection), but was verified via the `AppTest`-based smoke test described
above rather than left unverified.
