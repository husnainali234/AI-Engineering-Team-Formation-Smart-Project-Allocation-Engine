# Day 15 — Checkpoint 3: Full Integration

## Goal

Per the execution guide's Week 3 plan: **"Full system run: import data ->
engines -> dashboards. Bug bash across the stack"** (Engineer A), plus
**"Internal dry-run demo; finalize Architecture Diagram v3"** (Engineer B).
No new engines today — Days 1-14 already built everything the system
needs. Day 15's job is to prove the whole chain actually holds together
end to end, not just that each day's own isolated tests pass.

## What "full system run" actually means here

Day 5's checkpoint proved `Import -> Embedding -> Skill Matrix`. Day 10's
checkpoint proved every engine wired together behind `/recommend-teams`.
Neither of those touches the last hop: that what `/recommend-teams`
persists is *exactly* what the three dashboards' own endpoints
(`/admin-analytics/*`, `/student/{id}/dashboard`) read back — not a
parallel computation that could silently drift from it. That's the one
integration seam Day 15 adds coverage for, by tracing:

```
POST /import
    -> DB rows + auto-generated embeddings (Day 3-4)
POST /recommend-teams
    -> team formation, compatibility, skill matrix, project fit,
       workload, success probability, risk, SHAP explanation
       (Days 6-11), persisted to Team / TeamMember (Day 10)
GET /admin-analytics/teams, /projects, /resource-utilization
    -> Mentor/Admin Dashboard data source (Day 13), rolling up exactly
       what /recommend-teams just persisted
GET /student/{id}/dashboard
    -> Student Dashboard data source (Day 14), same source-of-truth
       check from the individual student's side
```

## Bug found: success probability scale mismatch (Admin + Student dashboards)

Tracing that chain surfaced a real cross-day bug — the kind that no
single day's own unit tests could have caught, because each day's tests
were internally consistent with *that day's own* assumption about the
column, and only diverge once real data actually flows through all of
them together:

- `Team.compatibility_score` is persisted **0-100**.
- `Team.success_probability` is persisted **0-1**, deliberately, per the
  Day 1 ERD — both `POST /recommend-teams` (Day 10) and
  `POST /success-probability/team/{id}/recalculate` (Day 9) divide the
  engine's 0-100 output by 100 before writing it.
- Every endpoint that reports success probability to a client — Day 9's
  `/success-probability` response, Day 10's `/recommend-teams` response,
  and the Mentor Dashboard that renders the latter directly — reads the
  **live engine output** (0-100) and never touches the persisted column.
  The 0-1 storage convention stayed invisible everywhere the number was
  actually shown.
- Day 13's `admin_analytics_service.py` and Day 14's
  `student_dashboard_service.py` were the first code in the system to
  read the **persisted column** back out for display, and passed the raw
  0-1 value straight through. Both dashboards format success probability
  as `f"{value:.0f}%"` — written against the 0-100 convention every other
  screen already uses. Net effect: a team scoring a genuine ~72% would
  have rendered as **"1%"** on the Admin and Student Dashboards
  specifically.
- Each day's own unit tests missed it because they set synthetic values
  like `team.success_probability = 70.0` directly on the column —
  internally consistent with what that day's own assertions expected, but
  not with the real 0-1 range the column holds once `/recommend-teams`
  actually writes to it.

### Fix

- `app/services/admin_analytics_service.py` now defines
  `SUCCESS_PROBABILITY_DB_TO_PCT = 100.0` and rescales at all three read
  sites: `cross_team_analytics`'s per-team summaries, its org-wide
  average, and `project_success_rates`'s per-project average.
- `app/services/student_dashboard_service.py` imports the same constant
  and applies it in `build_team_view`.
- `tests/test_admin_analytics_service.py` and
  `tests/test_student_dashboard_service.py` — the two existing tests that
  set `team.success_probability` directly were corrected to use a
  realistic 0-1 value (e.g. `0.70`) and assert the rescaled `70.0`
  output, matching what `/recommend-teams` and `/success-probability`
  actually persist.

## New: full-chain regression test

`tests/test_integration_day15_checkpoint.py` — the "internal dry-run
demo" scripted as a test instead of a manual click-through, so it stays
part of the regression suite rather than a one-off checked box:

- `test_full_pipeline_import_through_dashboards` — imports 8 interns via
  CSV, runs `/recommend-teams`, then checks that `/admin-analytics/teams`,
  `/admin-analytics/projects`, `/admin-analytics/resource-utilization`,
  and `/student/{id}/dashboard` (for every placed member, plus any
  unassigned interns) all agree with what `/recommend-teams` returned for
  the same run — not just that each endpoint responds with *some* data.
  This is the test that would have caught the success-probability bug
  directly: it asserts `/admin-analytics/teams`' reported
  `success_probability` for a team matches `/recommend-teams`' own value
  for that same team, rounded to 2 decimals.
- `test_recommend_teams_output_is_stable_source_of_truth_for_technology_distribution`
  — confirms Day 4's `/skill-matrix/technology-frequency` (which the
  Admin Dashboard's Technology Distribution panel reuses rather than
  recomputing) still sees interns brought in through `/import`, not just
  ones created directly via `/interns` (which is all Day 4's own tests
  cover).

## Architecture Diagram v3

`ARCHITECTURE.md` is finalized as v3: the Day 5 (v1) and Day 7-9 sections
are unchanged, with new sections appended for Day 10's integration layer
(`/recommend-teams` orchestrating every engine), Day 11's explainability
layer (SHAP attached to every success-probability response), Days 12-14's
three dashboards and what each one reads, and this checkpoint's bug
writeup. First version of the document that shows the complete system
end to end, per the guide's "finalize the diagram" instruction.

## No other integration gaps found

The `/recommend-teams` response shape, the workload-persistence path
(`suggested_responsibility` only populated when a project actually
matched), and all three dashboards' field access were traced against
`app/schemas.py` and found consistent. Nothing else in the stack showed
the pattern the success-probability bug did (a value computed one way for
live API responses and persisted a different way for later reads).

## Verification

```bash
docker compose exec backend pytest tests/ -v
```

175 test functions across `tests/` as of Day 15 (2 new in
`test_integration_day15_checkpoint.py`, on top of Days 1-14's suite) —
run the command above to confirm the full count passes in your
environment, since this checkpoint's fix touches test expectations in
two existing files (`test_admin_analytics_service.py`,
`test_student_dashboard_service.py`) alongside the new integration test.

**Manual dry-run**, for the demo itself: bring the stack up
(`docker compose up`), open the Streamlit dashboard, import a CSV of
interns on the Admin page, run team recommendations from the Mentor page,
then confirm the Admin and Student Dashboards now show a realistic
success-probability percentage (not a value near 0%) for the teams just
formed — that's the visible symptom the Day 15 fix resolves.

## Week 3 checkpoint: passed

Full chain (import -> engines -> both dashboards) verified consistent
end to end; one cross-day scale bug found and fixed; Architecture
Diagram finalized at v3.
