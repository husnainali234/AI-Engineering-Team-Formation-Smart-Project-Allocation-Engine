# Day 14 — Student Dashboard + UI Polish

## Goal

Per the execution guide: Engineer A builds the Student Dashboard endpoint
(assigned team, role, compatibility score, strengths, responsibilities);
Engineer B builds the Student Dashboard frontend and unifies styling and
loading states across all three dashboards. End-of-day deliverable: **all
three dashboards complete and functioning end-to-end.**

## What's new since Day 13

```
ezitech-ai020/
├── app/
│   ├── services/
│   │   └── student_dashboard_service.py   # NEW — strengths, top skills, team view
│   ├── repositories/
│   │   └── intern_repository.py           # UPDATED — get_by_id_with_team_context()
│   ├── routers/
│   │   └── student_dashboard.py           # NEW — /student/{id}/dashboard
│   ├── schemas.py                         # UPDATED — Day 14 student dashboard schemas
│   └── main.py                            # UPDATED — router registered, student-dashboard tag, version 0.14.0
├── dashboard/
│   ├── lib/ui.py                          # NEW — shared loading()/fetch_error()/action_error()/empty_state()
│   ├── pages/3_🎓_Student_Dashboard.py     # REPLACED — Day 11 preview -> full dashboard
│   ├── pages/1_🧑‍🏫_Mentor_Dashboard.py    # UPDATED — now uses lib/ui.py
│   ├── pages/2_🛠️_Admin_Dashboard.py       # UPDATED — now uses lib/ui.py
│   └── Home.py                            # UPDATED — now uses lib/ui.py, nav copy reflects all 3 dashboards done
└── tests/
    ├── test_student_dashboard_service.py  # NEW
    └── test_router_student_dashboard.py   # NEW
```

## Track A — Student Dashboard endpoint

One new read-only endpoint: `GET /student/{intern_id}/dashboard`. Like
Day 13's `admin-analytics` router, there's no `/recalculate` here — this
reads what other engines already computed and persisted, plus a small
amount of rule-based derivation for "strengths" (nothing here is ML).

### Assigned team + role

Read from the `TeamMember` row. An intern could in principle sit on more
than one `TeamMember` row — nothing in the schema forbids it beyond one
row per `(team_id, intern_id)` pair — but every engine in this system
(Team Formation's default candidate pool, Workload, Risk Analysis)
already treats "assigned" as a single team. The router takes
`team_memberships[0]` rather than inventing multi-team semantics nothing
else in the codebase supports.

### Compatibility score / success probability

Read straight off the `Team` row — whatever the last Day 6/Day 9/
`recommend-teams` run wrote. No recomputation, same "read persisted state"
approach Day 13's `cross_team_analytics()` takes.

### Responsibility

`TeamMember.suggested_responsibility` — the field Day 8's
`POST /workload/team/{id}/apply` persists. It's `None` until that endpoint
has been run for the student's team; the dashboard treats that as "not
assigned yet" rather than surfacing an error, since a team that has a
project but hasn't had workload distribution run is a completely normal
mid-pipeline state.

### Strengths

Rule-based, mirroring Day 7's Leadership Detection and Day 9's Risk
Analysis: a student reading their own dashboard needs each callout tied
to a real number, not a vague compliment with nothing behind it.
`identify_strengths()` checks five signals against fixed thresholds —
leadership score, communication score, case-study performance,
attendance, GitHub contributions — and appends one plain-language line
per signal that clears its bar, followed by up to `TOP_SKILL_COUNT` (3)
skills at/above proficiency 4 from `top_skills()`. An intern with nothing
above threshold gets an empty list, not a forced compliment — same
"absence of data isn't evidence, but it's also not something to
manufacture" stance the rest of the codebase takes.

`top_skills()` only ranks structured `InternSkill` rows (which carry a
1-5 proficiency); `technology_stack` tokens — the only skill signal
`/import` populates — have no proficiency to rank by, so they're excluded
rather than assigned a fake one.

### Repository addition

`InternRepository.get_by_id_with_team_context()` — one query,
`joinedload`-ing the intern's skills, their `team_memberships` →
`team` → `project`, and `team_memberships` → `team` → `members` →
`intern` (for teammate names), instead of the naive four separate
lookups (`get intern`, `get team`, `get project`, `get teammates`) the
same view would otherwise need.

### API surface

`app/main.py` registers the new router and adds a `student-dashboard` tag
description; version bumped to `0.14.0`. 19 route groups total now (18
through Day 13, +1 today).

## Track B — Student Dashboard frontend + UI unification

### Student Dashboard

`dashboard/pages/3_🎓_Student_Dashboard.py` replaces the Day 11
"look yourself up" preview (which just dumped raw `st.json` of
`/interns/{id}`) with a real dashboard: team name, role, compatibility/
success-probability metrics, project, responsibility, teammate list, and
strengths/top-skills — all from the single Day 14 endpoint call. The
"enter your intern ID and look yourself up" interaction pattern from the
Day 11 scaffold is preserved, since it's still the right UX for a page
with no auth layer to know who's asking.

### UI unification (`dashboard/lib/ui.py`, new)

Before today, each dashboard page had its own copy of the same three
patterns:

- a spinner around a fetch (`st.spinner("...")`, worded differently per
  page and not applied consistently — the Day 13 Admin Dashboard's GET
  calls had no spinner at all, only the Day 12 Mentor Dashboard's POST
  did),
- an `st.error(f"Could not reach the backend: {x}")` for an unreachable
  backend, copy-pasted into three files,
- an `st.info("...")` for "no data yet", with each page phrasing it
  slightly differently.

`lib/ui.py` centralizes all four patterns needed across the three pages:

- `loading(message)` — a context manager wrapping `st.spinner`, so every
  page's loading copy goes through one place.
- `fetch_error(payload)` — standard rendering for a failed `get_json`
  call.
- `action_error(action, payload)` — same shape, but for a failed
  `post_json` (e.g. `/recommend-teams` returning a 409) — kept distinct
  from `fetch_error` because "the backend is unreachable" and "the action
  itself failed" are different failure modes worth different copy.
- `empty_state(message)` — standard `st.info` rendering for "nothing here
  yet".

All four pages (`Home.py`, Mentor, Admin, Student) now import from
`lib/ui.py` instead of writing `st.spinner(...)` / `st.error(f"Could not
reach...")` inline — this is what "unify styling and loading states
across all three dashboards" means concretely. `Home.py`'s nav copy also
dropped the `*(full content: Day N)*` placeholders next to each
dashboard's bullet, since all three are now real.

## Verification

Same approach as Days 12-13 — checked end-to-end rather than just read
back:

1. Booted the FastAPI backend against a throwaway in-memory SQLite
   database, same as every prior day.
2. Seeded an intern with no team (confirms `team: null`, not a 404), an
   intern on a team with no project yet, and an intern on a team with a
   project and workload already applied via
   `POST /workload/team/{id}/apply` — to exercise all three states
   `suggested_responsibility` can be in.
3. Seeded skills across a mix of proficiencies to confirm `top_skills()`
   ranks and truncates correctly and excludes `technology_stack`-only
   entries.
4. Called `GET /student/{id}/dashboard` directly to confirm the response
   shape matches exactly what the dashboard reads (`dashboard["team"][
   "teammates"]`, `dashboard["strengths"]`, `dashboard["top_skills"]`).
5. New pytest coverage: `test_student_dashboard_service.py` (5 tests —
   strengths above/below threshold, skill ranking and exclusion,
   teammate-exclusion in `build_team_view`) and
   `test_router_student_dashboard.py` (4 tests — 404 for an unknown
   intern, no-team state, assigned-team state, and the applied-workload
   state through the live `/workload/team/{id}/apply` → `/student/{id}/
   dashboard` round trip).

## Running everything

```bash
docker compose exec backend pytest tests/ -v
```

174 tests pass across Days 1-14 (165 through Day 13, +9 today). As with
Days 12-13, the Streamlit pages themselves have no pytest suite — their
correctness is covered by the backend endpoint tests above plus the
manual HTTP verification in steps 2-4.
