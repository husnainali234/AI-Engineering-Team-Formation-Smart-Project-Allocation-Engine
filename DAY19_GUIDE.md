# Day 19 — Presentation

## Goal

Per the execution guide: **"Build Technical Presentation slides: problem,
architecture, AI engines, explainability, results"** (Engineer A) and
**"Prepare and rehearse the live demonstration script covering every
evaluation criterion"** (Engineer B). Deliverable: "Presentation deck
complete; demo rehearsed once end-to-end."

No code changes today — this is the one day in the plan that's entirely
presentation and rehearsal, not implementation. Day 18's engines, routers,
and tests are untouched.

## What's new since Day 18

```
ezitech-ai020/
├── presentation/
│   └── AI-020_Technical_Presentation.pptx   # NEW — 15-slide deck
└── DEMO_SCRIPT.md                            # NEW
```

## 1. Technical Presentation deck (Engineer A)

15 slides, built with `pptxgenjs` per the pptx skill's guidance (a navy /
ice-blue palette with one teal accent — chosen for a technical/enterprise
topic, not a default blue):

1. **Title**
2. **The Problem** — pain points a manual matching process hits
3. **Solution at a glance** — real stat callouts pulled from this repo
   (21 router modules, 18 service modules, 3 dashboards, 37 test files)
4. **System Architecture** — a lane diagram (Clients → API → Services →
   Data/ML), condensed from `ARCHITECTURE.md`'s v4 diagram
5. **Tech stack** — table reflecting what was actually built (no Neo4j/
   NetworkX knowledge graph or Redis caching — those were optional/bonus
   items in the original plan that weren't implemented; the slide
   doesn't claim otherwise)
6. **The pipeline** — Import → Embed → Match → Form Teams → Recommend
   Project → Score → Explain
7-9. **Three engine spotlights** — Matching & Compatibility, Team
   Formation & Leadership, Success Probability & Risk
10. **Explainability** — SHAP contribution bar chart (illustrative
    values, labeled as such — see DEMO_SCRIPT.md's note on why)
11. **Innovation (Day 16 bonus features)**
12. **Results & Validation** — test-file/test-function counts, both
    labeled as grep-counted from the repo, not a live pytest run
13. **Evaluation criteria mapping** — the rubric's own 7 criteria and
    weights, each mapped to where it's earned in this build
14. **Deployment**
15. **Closing**

Verified: `validate.py` passed with no structural errors; `markitdown`
found no leftover placeholder text; every slide was rendered to an image
and visually inspected for overflow, overlap, and alignment before being
called done.

## 2. Live demo script (Engineer B)

`DEMO_SCRIPT.md` — organized around the same 7 grading criteria, in
weight order, so a live walkthrough hits every one of them by
construction rather than touring the API in an arbitrary order.

**Important — read this before presenting.** Unlike Days 1-18, this
script was **not** produced against a running instance of the app. The
authoring environment used to write it has no Docker daemon and no
network route to PyPI or Hugging Face, so `docker compose up` and
`pip install` could not be executed here — a harder constraint than the
"no Hugging Face access" limitation noted in earlier days' guides, which
at least had a working local Postgres/uvicorn stack to fall back to.

Rather than inventing plausible-looking curl output and presenting it as
captured, `DEMO_SCRIPT.md`'s example responses were reconstructed from
this repo's own passing test assertions (`tests/test_router_*.py`),
which pin down exact field names, score ranges, and structural
invariants (e.g. `/team-chemistry` always returns exactly 4 named
components; `/success-probability`'s explanation always carries exactly
3 factors). Those shapes are trustworthy because they're asserted in
checked-in tests. The specific illustrative numbers are not live-captured
and are labeled as such in the script itself.

**What still needs to happen, on a normal developer machine, before this
is actually "rehearsed" per the day's own deliverable wording:**

- Run the real `docker compose up --build -d` + seed + embeddings-generate
  sequence from `DEMO_SCRIPT.md`'s Setup section.
- Actually execute every command in the script against that running
  instance.
- Re-create the two chemistry-contrast teams by ID range (documented as a
  known gotcha in the script: `/recommend-teams` reclusters the whole
  pool and will not preserve a curated two-team split) and confirm the
  leadership-conflict flag genuinely differs between them on your seeded
  data.
- Run `pytest tests/ -v` for the real, current pass count — grep counted
  37 test files / 212 `def test_...` functions directly from source,
  which is a real number but not the same thing as a pytest run
  confirming they all pass today.

None of this requires code changes — Day 18's engines are unchanged — it
requires a machine with Docker and internet access, which this sandboxed
session did not have. `DEMO_SCRIPT.md` calls this out explicitly in its
own closing section so whoever gives the actual presentation knows
exactly what's verified-by-test versus what's still pending a live run.

## Tests

No code changed today, so no new tests, and the existing suite was not
re-run in this session (see above — no way to install dependencies here).
Before treating Day 19 as closed, run:

```bash
docker compose exec backend pytest tests/ -v
```

and confirm it still reports all passing, unchanged from Day 18's count,
since it hasn't been exercised since then.
