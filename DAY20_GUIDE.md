# Day 20 — Final QA & Submission

## Goal

Per the execution guide: **"Final QA pass on all engines and APIs; fix
remaining bugs; verify explanation outputs are sensible"** (Engineer A) and
**"Verify deliverables checklist is 100% complete; package and submit repo,
docs, and presentation"** (Engineer B). Deliverable: "Project submitted —
all deliverables complete, demo tested twice, presentation finalized."

**This deliverable wording is not fully achievable in this session, and
this guide says so plainly rather than marking it done anyway** — see
`FINAL_DELIVERABLES_CHECKLIST.md`. The engines, routers, and docs are
complete; the "demo tested twice" clause specifically requires a live run
this sandboxed environment cannot perform (no Docker daemon, no PyPI/
Hugging Face network access — same constraint noted in `DAY19_GUIDE.md`).

## What's new since Day 19

```
ezitech-ai020/
├── FINAL_DELIVERABLES_CHECKLIST.md         # NEW
├── DAY20_GUIDE.md                           # NEW
├── README.md                                # CHANGED — added "Known limitations"; status table updated
├── app/services/explainability_service.py   # CHANGED — bug fix, see below
└── tests/test_explainability_service.py     # CHANGED — regression test for the fix
```

## 1. Final QA pass on engines and APIs (Engineer A)

Since this session cannot execute the app or its test suite (no
dependencies installable — confirmed again today, same as Day 19), "QA"
here means what's actually possible without execution: a full static
read-through of every service module for logic errors, a repo-wide scan
for leftover TODO/FIXME/placeholder markers, and — per the deliverable's
specific ask — reading `explainability_service.py` closely enough to
confirm its explanation output is *actually* sensible, not just
structurally present.

**One real bug found and fixed:** `explain_success_probability`'s
`reasons` list was built in fixed feature-declaration order
(`team_balance`, `avg_attendance_pct`, `avg_feedback_score`, always in
that order) instead of impact order. `summary` already correctly named
whichever feature had the largest SHAP magnitude as the "strongest
driver" — but `reasons[0]` would still describe `team_balance` first even
when it wasn't the top factor, so the two fields could contradict each
other in the same API response. Traced the cause to `reasons` being
zipped over `features` (the fixed declaration order) instead of `ranked`
(the same impact-sorted list `summary` uses). Fixed by building `reasons`
from `ranked` instead, and added a regression test that deliberately
constructs a lopsided input where `team_balance` is unlikely to be the
top factor, then asserts `summary` and `reasons[0]` name the same
feature.

This fix was verified by tracing the logic and by-hand-checking that no
existing test asserts a specific `reasons` order (only `len(reasons) == 3`
and truthiness are asserted elsewhere) — so it doesn't break anything
that was passing before. It has **not** been confirmed by an actual
`pytest` run, for the same dependency-installation reason as Day 19.
**Run `pytest tests/test_explainability_service.py -v` before trusting
this fix is fully correct.**

No other bugs were found. The repo-wide scan for `TODO|FIXME|XXX|
placeholder|lorem ipsum` returned only legitimate documentation
references to those words (e.g. "not a placeholder message" in
`DAY9_GUIDE.md`, "placeholder/preview calls" describing the dashboard's
intentional pre-live-data stub state in `dashboard/lib/api_client.py`) —
no actual unfinished code.

## 2. Deliverables checklist + packaging (Engineer B)

`FINAL_DELIVERABLES_CHECKLIST.md` cross-checks all 10 items from the
execution guide's Section 7 against this repo's actual current contents.
**9 of 10 are genuinely complete.** The one gap — item 9, "live
demonstration, rehearsed at least twice" — is real and is called out by
name rather than glossed over: `DEMO_SCRIPT.md` is fully written and its
example response shapes are verified against real test assertions, but it
has never been executed against a running instance in any session that
produced Days 19-20.

Closing this gap requires a machine with Docker and internet access. It
does not require any further code changes — everything it needs already
exists. The checklist spells out the exact four steps left (run the
stack, walk the script twice, capture a real pytest count, optionally
deploy for a live URL).

Also closed today: the README's "Known limitations" section, the one
component of deliverable #7 that was missing (setup/run
instructions/features/tech stack were already present; known limitations
was not). Added seven items, each verified against actual repo behavior
rather than boilerplate — e.g. the `/recommend-teams`-doesn't-preserve-
curated-teams gotcha already discovered and documented in
`DEMO_SCRIPT.md`, restated here as a limitation rather than just a demo
footnote.

## Tests

One new regression test added
(`tests/test_explainability_service.py::test_reasons_are_ordered_by_impact_matching_summary`).
Neither this test nor the rest of the suite has been executed in this
session — see the repeated dependency-installation note above. Before
treating Day 20, or the project, as closed:

```bash
docker compose exec backend pytest tests/ -v
```

confirm all tests pass (the new one included), then work through
`FINAL_DELIVERABLES_CHECKLIST.md`'s remaining steps for item 9 before
calling this submitted.
