# Final Deliverables Checklist

Cross-checked item by item against this repository's actual contents (not
assumed complete because a prior day's guide said so). Source: Section 7
of `AI-020_Execution_Guide.docx`.

**Post-Day-20 gap-fix pass:** a QA re-read against the *original case
study PDF* (not just the execution guide) found that "Engineering
Knowledge Graph" — listed under the PDF's AI Architecture Requirements,
independently of the suggested-technologies table — had been designed
(Day 1's tech-choice table picked NetworkX in-process over Neo4j) but
never actually built in Days 1-20. It's now implemented:
`app/services/knowledge_graph_service.py`, `/knowledge-graph/*` router,
20 new tests (`test_knowledge_graph_service.py`,
`test_router_knowledge_graph.py`). All counts and statuses below reflect
that addition.

| # | Deliverable | Status | Evidence |
|---|---|---|---|
| 1 | Complete source code (backend, ML engines, dashboards) in a GitHub repo | ✅ | `app/` (21 routers, 18 services, `app/ml/`), `dashboard/` (3 role pages) |
| 2 | AI Architecture Diagram (final) | ✅ | `ARCHITECTURE.md` — v5, post-Day-20, adds the Knowledge Graph engine |
| 3 | Team Recommendation Engine + Skill Matching Algorithms (code + write-up) | ✅ | `app/services/matching_service.py`, `team_formation_service.py`, `recommend_teams_service.py`; documented in `ARCHITECTURE.md` and `API_DOCUMENTATION.md` |
| 4 | API Documentation (Swagger/OpenAPI + annotated README) | ✅ | Live at `/docs`; `API_DOCUMENTATION.md`; README's "Route groups at a glance" |
| 5 | Database Design document (ERD + table descriptions) | ✅ | `DATABASE_DESIGN.md` |
| 6 | Deployment Guide (Docker Compose + optional live URL) | ✅ | `DEPLOYMENT_GUIDE.md`; `render.yaml` / `railway.json` / `fly.toml` present. **Live URL: not filled in** — none of the three configs has been actually deployed from this session; add the real URL once deployed |
| 7 | README (setup, run instructions, features, tech stack, known limitations) | ✅ | All five present as of Day 20 — "Known limitations" section was the one gap, added today |
| 8 | Technical Presentation slide deck | ✅ | `presentation/AI-020_Technical_Presentation.pptx` — 15 slides, schema-validated, visually QA'd |
| 9 | Live demonstration, rehearsed at least twice | ❌ **Not satisfied** | `DEMO_SCRIPT.md` is written and every response shape in it is verified against real test assertions, but it has never actually been run against a live instance — not once, let alone twice. See "What this means for submission" below. |
| 10 | At least one bonus challenge implemented (two if time allows) | ✅ (two) | Automatic Team Rebalancing + Team Chemistry Prediction, both Day 16, both covered by their own router test files |

**9 of 10 fully satisfied. Item 9 is genuinely open** — it requires a
machine with Docker and internet access, which none of the sessions that
produced Days 19-20 had. This isn't a paperwork gap that can be closed by
writing another document; it requires actually running the app.

## What this means for submission

Do not mark Day 20 or the project as "submitted — demo tested twice" until
someone has actually:

1. Run `docker compose up --build -d` + seed + `POST /embeddings/generate-all`
   on a real machine.
2. Walked through every command in `DEMO_SCRIPT.md` against that running
   instance, end to end, **twice**, confirming each response and fixing
   anything that doesn't match (start with the two known gotchas already
   documented in the script: the chemistry-demo teams must be created
   directly by ID range, and embeddings must be generated before
   `/recommend-teams` will return anything).
3. Run `pytest tests/ -v` for a real, current pass count and dropped it
   into `DEMO_SCRIPT.md`'s Closing section in place of the "state whatever
   number your run reports" placeholder.
4. Optionally, actually deployed to Render/Railway/Fly and filled in a
   real live-demo URL in `DEPLOYMENT_GUIDE.md` and this checklist's row 6.

Everything else on this checklist is genuinely done and doesn't need
revisiting.

## Day 20 code-level QA findings

One real (minor, non-blocking) bug was found and fixed during this pass:

- **`explainability_service.explain_success_probability`'s `reasons` list
  was built in fixed feature-declaration order, not impact order.** This
  meant `reasons[0]` could name a different feature than `summary`'s
  "strongest driver" claim whenever a feature other than `team_balance`
  actually had the largest SHAP magnitude — a real inconsistency a mentor
  reading both fields side by side could have noticed. Fixed to build
  `reasons` from the same impact-ranked order `summary` already used, with
  a new regression test (`test_reasons_are_ordered_by_impact_matching_summary`
  in `tests/test_explainability_service.py`) asserting the two can never
  disagree again. This is a real, traced-through-the-code fix — not a
  cosmetic change — but like everything else in Days 19-20, it has not
  been confirmed by an actual `pytest` run in this environment (still
  blocked on the same missing-dependencies issue noted in
  `DAY19_GUIDE.md`). Run the suite to confirm before trusting it fully.

No other bugs were found in a static read-through of
`app/services/*.py` and a repo-wide scan for leftover TODO/FIXME/
placeholder markers (clean — the only hits were legitimate documentation
references to the word "placeholder," not actual unfinished code).
