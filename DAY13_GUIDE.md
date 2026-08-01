# Day 13 — Admin Dashboard

## Goal

Per the execution guide: Engineer A builds Admin analytics endpoints
(cross-team analytics, project success rates, tech distribution, resource
utilization); Engineer B builds the Admin Dashboard frontend with charts
for those metrics. End-of-day deliverable: **Admin dashboard functional,
pulling from real aggregation endpoints.**

## What's new since Day 12

```
ezitech-ai020/
├── app/
│   ├── services/
│   │   └── admin_analytics_service.py     # NEW — cross-team, project, resource-utilization aggregation
│   ├── repositories/
│   │   ├── team_repository.py             # UPDATED — list_all_with_project_and_members(), assigned_intern_ids()
│   │   └── project_repository.py          # UPDATED — list_all_with_teams()
│   ├── routers/
│   │   └── admin_analytics.py             # NEW — /admin-analytics/*
│   ├── schemas.py                         # UPDATED — Day 13 admin analytics schemas
│   └── main.py                            # UPDATED — router registered, admin-analytics tag, version 0.13.0
├── dashboard/
│   ├── pages/2_🛠️_Admin_Dashboard.py       # REPLACED — Day 11 preview -> full Plotly dashboard
│   └── requirements.txt                   # UPDATED — + plotly
└── tests/
    ├── test_admin_analytics_service.py    # NEW
    └── test_router_admin_analytics.py     # NEW
```

## Track A — Admin analytics endpoints

Three new `GET /admin-analytics/*` endpoints, all read-only. Unlike
`risk-analysis` or `success-probability`, there's no `/recalculate` here —
these are rollups over data other engines already wrote (`Team.
compatibility_score`, `Team.success_probability`, `Team.risk_notes`) or
plain headcounts, so there's nothing new to persist.

### `GET /admin-analytics/teams` — cross-team analytics

Team-size distribution, project-assignment counts, risk-assessment counts,
and average compatibility/success scores across every team — plus a
per-team summary row for the dashboard's table.

The one design decision worth calling out: `Team.compatibility_score` and
`Team.success_probability` both default to `0.0` (see `app/models.py`) for
a team that was created via the plain CRUD endpoint and never run through
the Day 6/Day 9 engines or `POST /recommend-teams`. Averaging those
untouched `0.0`s in with genuinely-scored teams would silently drag every
org-wide average toward zero the moment an admin creates a team by hand —
the exact same "absence of data isn't evidence" problem Day 9's
`risk_analysis_service` already had to handle for the same two columns.
So `cross_team_analytics()` splits teams into "scored" (non-zero) and
"unscored" before averaging, and only blends the scored subset into
`avg_compatibility_score` / `avg_success_probability`. The unscored count
isn't hidden — it's implicit in `team_count` vs. how many teams actually
have a `risk_assessed: true` / non-zero score in the per-team table — an
admin can see at a glance which teams haven't been run through the
pipeline yet.

### `GET /admin-analytics/projects` — project success rates

Per project: how many teams have been matched to it (`team.project_id ==
project.id`, via the existing `Project.teams` relationship) and their
average success probability / compatibility score. Projects with zero
matched teams are included with `team_count: 0` and `null` averages rather
than omitted — "which projects nobody has been assigned to yet" is exactly
the kind of gap an admin dashboard exists to surface.

### `GET /admin-analytics/resource-utilization` — org-wide headcount

How much of the intern pool is already committed to a team vs. still
sitting in the candidate pool for the next Team Formation run
(`available_and_unassigned_count` — the same "available AND unassigned"
condition `InternRepository.list_available_unassigned_with_embeddings()`
already filters by for Day 7's default candidate pool, just counted here
instead of listed), plus a couple of data-readiness signals an admin would
want on one screen: embedding coverage and org-wide attendance/case-study/
credit averages.

### Technology distribution — intentionally not a new endpoint

The execution guide names four Day 13 metrics; only three got new
endpoints. Technology distribution is exactly Day 4's existing
`GET /skill-matrix/technology-frequency` called with no `team_id` (already
org-wide scope) — duplicating that aggregation into
`admin_analytics_service` would just be two functions computing the same
`Counter` over the same interns. The Admin Dashboard calls the Day 4
endpoint directly instead, the same reuse-over-duplicate call the Mentor
Dashboard made on Day 12 for the pairwise compatibility breakdown
(`GET /compatibility/team/{id}`).

### Repository additions

Two small additions, following the "add what's needed, don't pre-build"
pattern every prior day's repository layer has used:

- `TeamRepository.list_all_with_project_and_members()` — every team's
  project and member list in one query (`joinedload` on both), not
  fetch-one-at-a-time.
- `TeamRepository.assigned_intern_ids()` — the same "already on a team"
  set `InternRepository.list_available_unassigned_with_embeddings()`
  computes as a subquery filter, pulled out as a standalone method so
  Resource Utilization can classify *every* intern as assigned/unassigned
  regardless of availability or embedding status (the existing subquery is
  private to that one method and combined with two other filters, so it
  wasn't reusable as-is).
- `ProjectRepository.list_all_with_teams()` — every project with its
  matched teams (`joinedload(Project.teams)`) in one query.

No changes to `InternRepository` — `list_all()` from Day 1-3 is already
exactly what Resource Utilization needs.

### API surface

`app/main.py` registers the new router and adds an `admin-analytics` tag
description; version bumped to `0.13.0`. 18 route groups total now (17
through Day 12, +1 today).

## Track B — Admin Dashboard

`dashboard/pages/2_🛠️_Admin_Dashboard.py` replaces the Day 11 preview
(intern/project counts only) with all four metrics from the execution
guide, each backed by a real aggregation endpoint:

1. **Cross-Team Analytics** — summary metrics (team count, avg
   compatibility, avg success probability, teams flagged at risk), a
   team-size histogram, a project-assignment pie chart, and a full
   per-team data table.
2. **Project Success Rates** — a bar chart of teams matched per project
   (color-scaled by average success probability, so an admin can spot a
   project with many teams but a low average at a glance) plus the full
   per-project table, including projects with zero matches.
3. **Technology Distribution** — top 20 technologies org-wide, as a
   horizontal bar chart, pulled from `/skill-matrix/technology-frequency`.
4. **Resource Utilization** — assigned/unassigned pie chart, org-wide
   average metrics (attendance, case study, credits) as a bar chart, plus
   headline metrics for total interns, assigned %, available candidate
   pool, and embedding coverage.

Charts use Plotly (`plotly.express`) via `st.plotly_chart` — the guide
lists Plotly first for the Admin Dashboard, and its `color=` encoding on
the project bar chart is a genuinely better fit than Streamlit's built-in
`st.bar_chart` for the "count + a second dimension" chart in section 2.
`dashboard/requirements.txt` gained `plotly==5.24.1` accordingly.

Every section handles the "not reachable" / "no data yet" cases the same
way earlier dashboard pages do — `get_json`'s `(ok, payload)` tuple is
checked before rendering, with an `st.info`/`st.error` fallback instead of
a raw exception, so an empty database (a fresh clone before Day 2's seed
script has run) produces a readable page instead of a stack trace.

## Verification

Same approach as Day 12 — checked end-to-end rather than just read back:

1. Booted the FastAPI backend against a throwaway in-memory SQLite
   database (`DATABASE_URL` override, same as every prior day).
2. Seeded interns, projects, and teams (a mix of CRUD-created teams and
   ones with `compatibility_score`/`success_probability` set) directly via
   HTTP and the test factories, to exercise both the "scored" and
   "unscored" paths in `cross_team_analytics()`.
3. Called all three `/admin-analytics/*` endpoints directly to confirm the
   response shapes match exactly what the dashboard reads (`teams_data[
   "size_distribution"]`, `project_data["projects"]`, `util[
   "available_and_unassigned_count"]`, etc.).
4. New pytest coverage: `test_admin_analytics_service.py` (5 tests —
   scored-vs-unscored averaging, project/risk counting, projects without
   teams, resource-utilization splits, the empty-pool edge case) and
   `test_router_admin_analytics.py` (4 tests — empty state, populated
   state, a project with no matched team, intern-pool counts through the
   live API).

## Running everything

```bash
docker compose exec backend pytest tests/ -v
```

165 tests pass across Days 1-13 (156 through Day 12, +9 today). The Admin
Dashboard itself has no pytest suite of its own (Streamlit pages aren't
part of the backend's test collection, same as the Mentor Dashboard on
Day 12) — its correctness is covered by the backend endpoint tests above
plus the manual HTTP verification in step 3.
