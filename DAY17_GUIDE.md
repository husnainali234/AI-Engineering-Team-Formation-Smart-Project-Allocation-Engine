# Day 17 — Containerization + Docs Draft

## Goal

Per the execution guide: **"Finalize Docker Compose for the full stack;
add lightweight MLflow model-version tracking; clean up config/env
vars"** (Engineer A) and **"Write Database Design document, final
Architecture Diagram, and Deployment Guide"** (Engineer B). Deliverable:
`docker-compose up` runs the entire system from scratch; core docs
drafted.

No new tables, no new API routes — Day 17 is infrastructure and
documentation, not a new engine.

## What's new since Day 16

```
ezitech-ai020/
├── app/
│   ├── config.py                          # NEW — centralized pydantic-settings
│   ├── database.py                        # UPDATED — reads settings.DATABASE_URL
│   └── ml/
│       ├── embedding_model.py             # UPDATED — reads settings.EMBEDDING_MODEL_NAME
│       ├── mlflow_tracking.py             # NEW — lightweight, best-effort MLflow logging
│       └── success_probability_model.py   # UPDATED — logs each training run
├── tests/
│   └── test_mlflow_tracking.py            # NEW
├── docker-compose.yml                     # UPDATED — mlruns volume
├── .env.example                           # UPDATED — MLFLOW_* vars documented
├── requirements.txt                       # UPDATED — mlflow-skinny
├── ARCHITECTURE.md                        # UPDATED — v4, Day 16 + Day 17 sections
├── DATABASE_DESIGN.md                     # NEW
└── DEPLOYMENT_GUIDE.md                    # NEW
```

## 1. Config cleanup (Engineer A)

Before today, `DATABASE_URL` and `EMBEDDING_MODEL_NAME` were each read
via a direct `os.getenv` call at their own point of use
(`app/database.py`, `app/ml/embedding_model.py`) — workable at two env
vars, but Day 17 adds three more for MLflow, and "grep for `os.getenv`
to find every knob" doesn't scale. `pydantic-settings` had been sitting
in `requirements.txt` unused since Day 1 for exactly this.

`app/config.py` is now the single `Settings` object every env-driven
value flows through — same defaults as before for the two pre-existing
vars, so this is a pure refactor, not a behavior change, plus three new
ones for MLflow (`MLFLOW_TRACKING_URI`, `MLFLOW_EXPERIMENT_NAME`,
`MLFLOW_TRACKING_ENABLED`).

## 2. Lightweight MLflow model-version tracking (Engineer A)

Scope is deliberately narrow: there is exactly one trained model in this
system — Day 9's `success_probability_model`'s `LogisticRegression`,
lazily fit on synthetic data on first use. `app/ml/mlflow_tracking.py`
wraps that one training call with an MLflow run:

- **Params:** random seed, synthetic-sample count, feature names, model
  class
- **Metric:** train accuracy against the synthetic set it was fit on
- **Tag:** `model_version` — a short hash fingerprint of the params, so
  a run trained under different assumptions (e.g. a future change to
  `_N_SYNTHETIC_SAMPLES`) is visibly a different version without
  hand-bumping a version string every time

`mlflow-skinny`, not the full `mlflow` package, on purpose — the client
API without a bundled tracking server/UI process, logging against a
local `file:./mlruns` store by default (see `app/config.py`). This is
what makes it "lightweight": run history exists from the first
`docker compose up`, with no new service in `docker-compose.yml`, no new
port, nothing else to keep healthy. Point `MLFLOW_TRACKING_URI` at a
real tracking server later and no application code changes.

Tracking is **best-effort by construction** —
`log_success_probability_training` catches and logs every exception as a
warning instead of raising. A disk-full or unwritable-volume tracking
store must never turn a successful model train into a 500 on the first
`/success-probability` call: the model is the product, MLflow is
observability on top of it.

`docker-compose.yml`'s `backend` service gains an `./mlruns` bind mount
(same reasoning as the existing `pgdata`/`hf_cache` volumes: run history
survives container rebuilds/restarts).

## 3. Docker Compose finalization (Engineer A)

The three-service shape (`db`, `backend`, `dashboard`) from Day 11 was
already sound going into Day 17 — finalizing it meant the one addition
above (`mlruns` volume) plus confirming every env var the stack actually
uses is documented in `.env.example`, which it now is (`MLFLOW_*` added
alongside the existing `POSTGRES_*`/`DATABASE_URL`/`EMBEDDING_MODEL_NAME`
vars).

## 4. Database Design document (Engineer B)

`DATABASE_DESIGN.md` — the full ERD (mermaid) plus a per-table writeup of
every column and, notably, *which day's engine reads it* — several
columns (`project_interests`, `MentorFeedback.comments`) existed since
Day 1 but sat unread until Day 16's Team Chemistry signals, and the
writeup calls that out explicitly rather than presenting the schema as
if every column had always been fully used. Also documents the two
deliberate MVP tradeoffs already called out inline in `app/models.py`
(free-text `technology_stack`/`project_interests` instead of normalized
tables; a generic `JSON` embedding column instead of `pgvector`) and the
Day 15 checkpoint's `compatibility_score` (0-100) vs `success_probability`
(0-1) scale asymmetry, cross-referenced to `ARCHITECTURE.md` rather than
re-explained.

## 5. Final Architecture Diagram (Engineer B)

`ARCHITECTURE.md` retitled v3 → **v4 (Day 17 — Final)** and extended
in place (same pattern the file has followed since Day 5) with two new
sections:

- **Day 16 additions** — a diagram of the two bonus features' service
  layer and, importantly, everything they *reuse* rather than
  reimplement (Day 6's `cosine_similarity`, Day 7's `suggest_leader`,
  Day 10's `compute_team_recommendation`).
- **Day 17 additions** — a diagram of the new config/observability layer
  (`app/config.py`, `app/ml/mlflow_tracking.py`) and how it sits
  cross-cutting rather than adding request-flow routes, so the existing
  Day 4-15 flow diagrams didn't need to be redrawn.

## 6. Deployment Guide (Engineer B)

`DEPLOYMENT_GUIDE.md` — prerequisites, `.env` configuration (with every
variable's default and when to change it), bring-up, migrations/seeding,
verification (`/health`, Swagger, dashboard), running the test suite
inside the container, inspecting MLflow run history from the host, common
operations (teardown, rebuild, logs, shell), and a troubleshooting
section for the failure modes that actually come up locally (cold-start
timing, stale volumes, MLflow logging warnings). Scoped to the local/
self-hosted Compose deployment this project runs on today; Day 18's
guide builds on top of it for the hosted demo instance.

## Tests

- `tests/test_mlflow_tracking.py` — the tracking helper is disabled by
  default across the rest of the suite (autouse `conftest.py` fixture),
  and re-enabled locally here (against a `tmp_path` file store) to check:
  a run is logged with the right params/metric/tag shape; the same
  params always produce the same `model_version` tag and different
  params produce a different one; and a broken tracking backend (a path
  under a plain file, not a directory) never raises out of
  `log_success_probability_training`.

Run everything with:

```bash
docker compose exec backend pytest tests/ -v
```

209 test functions across `tests/` as of Day 17 (5 new in
`test_mlflow_tracking.py`, on top of Day 16's 204). Actually run locally
in the authoring environment this time (Day 15/16's guides note no
network access was available then to install the dependency stack; a
clean venv with `requirements.txt`'s pinned versions — `psycopg2-binary`
substituted for the missing driver, `sentence-transformers`/`torch`
skipped since `tests/conftest.py` monkeypatches around them entirely —
was used to confirm all 209 pass before writing this guide).

**Manual demo, for Day 17's changes specifically:** bring the stack up
with `docker compose up --build`, hit `GET /success-probability/team/{id}`
(or any endpoint that trains the model on first use) once, then either
`docker compose exec backend ls mlruns` (confirms the file store was
written inside the container) or, from the host,
`mlflow ui --backend-store-uri ./mlruns` to browse the logged run's
params/metric/`model_version` tag in a browser.
