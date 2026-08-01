# Day 18 — README + Deployment

## Goal

Per the execution guide: **"Write API Documentation (annotated) and
README (setup, run instructions, features, tech stack)"** (Engineer A)
and **"Deploy a live demo (Render/Railway/Fly.io free tier or local
network) with a curated demo dataset"** (Engineer B). Deliverable:
"README and API docs complete; demo environment accessible."

No new tables, no new API routes, no new engines — like Day 17, this is
docs/deployment, not a new feature day. One small code change
(`ALLOWED_ORIGINS`) exists only because it's a real prerequisite for the
hosted-demo half of the goal, not a new feature.

## A note on "demo environment accessible"

This environment (the one these guides are being written and tested in)
has network access scoped to a small allowlist for security reasons —
PyPI, npm, GitHub, and a few others — and does not include
Render/Railway/Fly.io. That means the actual "click deploy and get a
public URL" step can't be executed from here. What *is* done, so that
step is a copy-paste away rather than a from-scratch effort: every
config file a real deploy needs (`render.yaml`, `railway.json`,
`fly.toml`), a curated demo dataset script tuned for exactly the flows
someone would walk through in a live demo, and a step-by-step guide for
all three platforms in `DEPLOYMENT_GUIDE.md`. Whoever has an account on
one of these platforms can go from this repo to a public URL by
following `DEPLOYMENT_GUIDE.md`'s "Hosted demo" section directly — no
platform-specific research required, no missing env var, no guessing at
a start command.

The "local network" alternative the execution guide also allows is
already fully satisfied: `docker compose up --build -d` on any machine on
the network, reachable by anyone else on that network at that machine's
LAN IP on port 8501 (dashboard) / 8000 (API) — no code change needed for
that path, it's what `docker-compose.yml` has produced since Day 1.

## What's new since Day 17

```
ezitech-ai020/
├── app/
│   ├── config.py                    # UPDATED — + ALLOWED_ORIGINS / cors_origins
│   └── main.py                      # UPDATED — CORS reads settings.cors_origins
├── tests/
│   └── test_config_cors.py          # NEW — 4 tests for cors_origins parsing
├── scripts/
│   └── generate_demo_dataset.py     # NEW — curated 24-intern demo dataset
├── render.yaml                      # NEW — Render Blueprint (backend + dashboard + db)
├── railway.json                     # NEW — Railway build/start config
├── fly.toml                         # NEW — Fly.io app config (backend)
├── API_DOCUMENTATION.md             # NEW
├── DEPLOYMENT_GUIDE.md              # UPDATED — + "Hosted demo (Day 18)" section
└── README.md                        # UPDATED — Features / Tech Stack / Quick Start sections
```

## 1. API Documentation (Engineer A)

`API_DOCUMENTATION.md` — organized by engine/day rather than
alphabetically by path, since that's how someone new to the codebase
actually thinks about it ("show me the compatibility endpoints," not
"show me everything starting with C"). Deliberately doesn't restate
every field of every schema — Swagger (`/docs`) and `app/schemas.py`
already are that exhaustive reference, and a hand-maintained doc that
duplicates it just drifts out of sync over time. Instead it covers:

- A full endpoint table per engine (method, path, one-line purpose)
- The three-error-code convention (`404`/`409`/`422`) and *why* `409` is
  used instead of `404` for "exists but not ready" states — the
  reasoning, not just the code, which Swagger alone doesn't communicate
- Two full end-to-end example flows with real request/response JSON:
  `POST /recommend-teams` (every engine chained in one call) and the
  Day 16 rebalance → chemistry pair (verified against the actual
  `TeamFormationRequest`/`RecommendTeamsResultOut` schemas in
  `app/schemas.py`, not written from memory, after an initial draft used
  a field name — `n_teams` — that isn't real)

## 2. README polish (Engineer A)

Before today, `README.md` was effectively a running Day-1-through-17
project log — accurate, but someone landing on the repo cold had to
scroll past 17 days of history to find "what does this do" and "how do
I run it." Added, above the existing status table (kept intact — it's
still useful as a changelog):

- **Features** — one bullet per engine, each tagged with the day it
  shipped, so the list doubles as a map into the day-by-day guides
- **Tech stack** — a table, not prose, so it's scannable
- **Quick start** — the actual minimum command sequence to go from
  `git clone` to a running stack, cross-referenced to
  `DEPLOYMENT_GUIDE.md` for anything that goes wrong
- **Live demo** placeholder — a link to `DEPLOYMENT_GUIDE.md`'s hosted-
  demo section rather than a hardcoded URL, since no URL exists yet in
  this environment (see the note above) and a dead link would be worse
  than an honest pointer to "how to get one"

## 3. Live demo deployment (Engineer B)

Three platform configs, one per option the execution guide names:

- **`render.yaml`** — a full Blueprint: free Postgres, the backend
  service (Dockerfile-based, `$PORT`-aware start command overriding the
  Dockerfile's dev-mode `--reload`), and the dashboard service. One
  manual step is called out explicitly in a comment rather than silently
  assumed to work: Render's Blueprint templating can't reliably produce
  a scheme-prefixed cross-service URL, so `BACKEND_URL` needs a one-time
  manual paste after first deploy.
- **`railway.json`** — build/start override so Railway's Dockerfile
  auto-detection still ends up running the `$PORT`-aware production
  start command instead of the dev one.
- **`fly.toml`** — backend-only by design (see its header comment for
  why, and the documented alternative for the dashboard). Bumped from an
  initial 512mb to 1024mb after considering `torch` (via
  sentence-transformers) and `shap`'s memory footprint once the
  embedding model is actually loaded — 512mb risked an OOM on that
  specific request path.

**CORS.** All three configs assume `ALLOWED_ORIGINS` gets set to the
actual deployed origin once known — the `app/config.py`/`app/main.py`
change in this day's diff. Defaults to `"*"` so nothing breaks for
existing local-dev setups; a hosted deployment is the one case that
actually needs it tightened, which is exactly Day 1's original
`# tighten before deployment (Week 4)` comment on the CORS middleware,
now acted on.

## 4. Curated demo dataset (Engineer B)

`scripts/generate_demo_dataset.py` — 24 hand-tuned interns and 4
projects, distinct from Day 2's `generate_mock_data.py` (120 fully-random
interns, good for scale testing, not for a live walkthrough). Designed
around the specific flows a demo actually needs to show working, not
just "a demo can technically be given without an unavailable-intern
edge case":

- 8 interns forming a team with one unmistakable leader
  (`leadership_score=9.2`, next-highest well under 7.0)
- 8 more forming a team with two competing leaders (both `>= 7.0`) —
  side by side with the first team, `/team-chemistry` visibly shows the
  `leadership_balance` flag differ between them
- 2 interns pre-marked `is_available=False`, so `/rebalance/needed` has
  something to show immediately, no manual setup step first
- every intern gets both a positive- and friction-leaning mentor comment
  (from two small curated phrase pools), so the chemistry engine's
  `feedback_sentiment` signal reacts to real language instead of neutral
  filler text
- 4 projects with genuinely different required tech stacks, each
  actually matched by some intern's real stack

Verified by actually running it (against a throwaway SQLite file, since
this environment has no live Postgres) and querying the result back out:
24 interns seeded, exactly 2 unavailable, exactly 3 with
`leadership_score >= 7.0` (the intended 2 from the competing-leader team
plus the 1 clear leader from the other team), 4 projects, 14 skills, 48
feedback rows (2 per intern) — matching the script's own design intent
rather than just trusting that it ran without an exception.

## Tests

- `tests/test_config_cors.py` — `Settings.cors_origins` parsing:
  wildcard passthrough, single origin, multiple comma-separated origins
  (including whitespace trimming), and blank-entry filtering.

213 test functions total as of Day 18 (4 new here, on top of Day 17's
209). Run:

```bash
docker compose exec backend pytest tests/ -v
```

Actually run locally in the authoring environment against the same venv
used for Day 16/17 (pinned `requirements.txt` versions,
`psycopg2-binary` substituted for the driver, `sentence-transformers`
skipped since `conftest.py` monkeypatches around it) — all 213 pass.

**Manual verification for Day 18's changes specifically:** the demo
dataset script was run end-to-end against a throwaway SQLite database
(see above) rather than just read for correctness, since a seed script
that raises on `Base.metadata.create_all` or a `UniqueConstraint`
violation only shows up by actually executing it.
