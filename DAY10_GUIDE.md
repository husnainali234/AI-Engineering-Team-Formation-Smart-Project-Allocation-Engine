# Day 10 — Checkpoint 2: `/recommend-teams`

## Goal

Wire every engine built on Days 4-9 into a single integration endpoint so a
mentor (or the frontend) can go from "here's a pool of interns" to "here are
fully-formed, fully-scored, fully-staffed teams" in one API call, instead of
chaining ~8 separate requests together by hand.

## What it does

`POST /recommend-teams` — same request shape as Day 7's
`/team-formation/preview` and `/commit`:

```json
{
  "intern_ids": [1, 2, 3, 4, 5, 6, 7, 8],
  "team_size": 4,
  "algorithm": "kmeans"
}
```

`intern_ids` can be omitted, in which case the default candidate pool is
used (available, unassigned, and already-embedded interns — same default
Day 7's endpoints use).

For each candidate pool, the endpoint:

1. **Forms teams** — Day 7's `team_formation_service.form_teams` (KMeans or
   Agglomerative clustering into skill archetypes, then round-robin
   assembly for diversity).
2. **Persists the team + members** — creates the `Team` row and
   `TeamMember` rows, assigning `role="Lead"` to the suggested leader
   (Day 7's `leadership_service.suggest_leader`, already run inside
   `form_teams`).
3. **Scores the team** — `recommend_teams_service.compute_team_recommendation`
   runs, per team:
   - Day 6 `compatibility_service.team_compatibility` (pairwise, averaged)
   - Day 4 `skill_matrix_service.build_skill_matrix`
   - Day 8 `project_recommendation_service.recommend_projects` (top match)
   - Day 9 `success_probability_service.compute_success_probability`
   - Day 9 `risk_analysis_service.assess_risks`
4. **Persists the scores** — `Team.compatibility_score`, `Team.project_id`
   (if a project was matched), `Team.success_probability` (stored 0-1),
   `Team.risk_notes` (a formatted string built from the risk list).
5. **Distributes workload** — if a project was matched, Day 8's
   `workload_service.distribute_workload` runs against the now-persisted
   `TeamMember` rows (it needs real `role`/`team_id` values), and each
   member's `suggested_responsibility` is persisted.
6. **Blends an overall score** — `recommend_teams_service.OVERALL_SCORE_WEIGHTS`
   combines compatibility (0.35), success probability (0.35), project
   coverage (0.20), and skill diversity (0.10) into one 0-100 number for
   ranking/display. Weights sum to 1.0 (enforced by a test); if no project
   matched, that component's contribution is simply 0.

## Why the split between router and service

`app/services/recommend_teams_service.py` holds only the *pure* per-team
computation — compatibility → skill matrix → project fit → success
probability → risk → overall_score — none of which need a `Session`. That
keeps it unit-testable the same way `team_formation_service` and
`workload_service` already are (`tests/test_recommend_teams_service.py`,
built with `db_session`-created models, no `TestClient`).

`app/routers/recommend_teams.py` is deliberately *not* thin like the other
Day-4-9 routers — it owns candidate resolution, team formation, and all
persistence, because Day 10's job description *is* "orchestrate everything
that Days 4-9 built into one flow." Pushing that orchestration into a
service would just relocate the same code one file over without making it
any more testable, since it already needs a live `Session` for every step
that touches `TeamMember` roles.

## Error handling

Same failure modes as `/team-formation/preview` and `/commit`, since it
shares `team_formation_service.form_teams`:

- `404` — one or more `intern_ids` doesn't exist.
- `409` — fewer than 2 usable candidates, or one or more candidates is
  missing a skill embedding.
- `422` — unknown `algorithm`.

## Tests

- `tests/test_recommend_teams_service.py` — the pure scoring function:
  returns every expected key, handles the no-projects case, weights sum to
  1.0, and stronger team signals (attendance/leadership/communication)
  produce a higher `overall_score` than weaker ones.
- `tests/test_router_recommend_teams.py` — the full HTTP flow: 404/409
  error cases, a full run that checks every returned field is populated
  and persisted (`GET /teams/{id}` round-trip), workload only appears when
  a project was actually matched, and the default candidate pool behaves
  the same way `/team-formation` does.

Run everything with:

```bash
docker compose exec backend pytest tests/ -v
```

151 tests pass across Days 1-10 (in-memory SQLite, no network or real ML
model weights needed — `fake_embedding_model` monkeypatches the embedding
model the same way it does for Days 4-9).
