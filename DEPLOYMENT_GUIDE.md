# Deployment Guide

Written Day 17, covering the local/self-hosted Docker Compose deployment;
extended Day 18 with a "Hosted demo" section for standing up an
externally-accessible instance on a free-tier PaaS
(Render/Railway/Fly.io). Sections 1-6 are the prerequisite either way —
get the stack running correctly in one place first.

## Prerequisites

- Docker Engine + Docker Compose v2 (`docker compose version`)
- ~2GB free disk (mostly the sentence-transformers model weights + Docker
  image layers)
- Ports `8000` (API), `8501` (dashboard), and whatever `POSTGRES_PORT` you
  set (default `5432`) free on the host

No local Python install is required — everything runs inside containers.

## 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` if needed. Defaults work as-is for a local run; the values
worth knowing about:

| Variable | Default | When to change it |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `ezitech` / `ezitech_pass` / `ezitech_ai020` | Never required locally; change before any shared/hosted deployment |
| `POSTGRES_PORT` | `5432` | If `5432` is already taken on the host |
| `DATABASE_URL` | points at the `db` service | Only if you're running Postgres outside Docker Compose |
| `EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Swap for a different sentence-transformers model; larger models mean a slower first embedding call and a bigger `hf_cache` volume |
| `MLFLOW_TRACKING_URI` | `file:./mlruns` | Point at a real MLflow tracking server's URI if one exists; the app needs no code changes either way |
| `MLFLOW_EXPERIMENT_NAME` | `success-probability-model` | Cosmetic — groups runs in the MLflow UI |
| `MLFLOW_TRACKING_ENABLED` | `true` | Set `false` to disable model-version tracking entirely |

All of the above are read through `app/config.py`'s `Settings` object
(Day 17) — one place to check if a value doesn't seem to be taking
effect, rather than grepping for `os.getenv` across the codebase.

## 2. Start the stack

```bash
docker compose up --build
```

This brings up three services (see `docker-compose.yml`):

- **`db`** — Postgres 16, with a healthcheck gating the backend's startup
- **`backend`** — the FastAPI app (`app/main.py`), port `8000`
- **`dashboard`** — the Streamlit app (Mentor/Admin/Student views), port `8501`

First boot is slower than subsequent ones: the backend's Docker image
build installs the full dependency set (including `scikit-learn`, `shap`,
and `sentence-transformers`/`torch`), and the first request that touches
the embedding pipeline downloads the ~80MB `all-MiniLM-L6-v2` weights into
the `hf_cache` volume. Every restart after that reuses the cached weights.

Run detached for normal use:

```bash
docker compose up --build -d
```

## 3. Apply migrations and seed data

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/generate_mock_data.py
```

The seed script (Day 2) generates a realistic synthetic dataset (~120
interns, skills, projects) via Faker — the same dataset every day's
manual-demo steps assume exists.

## 4. Verify

```bash
curl http://localhost:8000/health
```

Expect `{"api": "ok", "database": "ok"}`. If `database` isn't `ok`, check
`docker compose logs db` — the most common cause locally is a stale
`pgdata` volume from a previous, incompatible schema version; see
Troubleshooting below.

- **API docs (Swagger UI):** http://localhost:8000/docs
- **Dashboards:** http://localhost:8501 (role-based nav: Mentor / Admin /
  Student — see `dashboard/Home.py`)

## 5. Run the test suite (optional, but recommended before any demo)

```bash
docker compose exec backend pytest tests/ -v
```

Runs against an in-memory SQLite DB inside the container (see
`tests/conftest.py`), not against the real Postgres — safe to run at any
time without touching seeded data. 209 tests as of Day 17 (see
`DAY16_GUIDE.md` / `DAY17_GUIDE.md` for the per-day breakdown).

## 6. Inspect MLflow run history (Day 17)

Tracking uses a local file store by default — no separate service to
start. From the host (with the `mlruns` volume populated after at least
one `/success-probability` call has trained the model):

```bash
pip install mlflow   # one-time, host-side only — not required to run the app
mlflow ui --backend-store-uri ./mlruns
```

Then open http://localhost:5000 to browse runs, params, and the
`model_version` tag. This is purely observability — the API never
depends on the MLflow UI being up.

## 7. Hosted demo (Day 18)

Everything above is the local Docker Compose deployment. This section
covers standing up an *externally accessible* demo instance on a free
tier — the Day 18 deliverable is "demo environment accessible," not a
durable production deployment, so all three options below trade
convenience for zero cost, which means occasional cold starts and
short-lived free databases. Pick whichever platform you already have an
account on; the app doesn't favor one over another.

### Option A — Render (recommended: least manual setup)

1. Push this repo to GitHub.
2. In the Render dashboard: **New +** → **Blueprint**, point it at the
   repo. Render reads `render.yaml` and provisions `ai020-db` (free
   Postgres), `ai020-backend`, and `ai020-dashboard` automatically.
3. Once `ai020-backend` has its first deploy, copy its `https://...
   onrender.com` URL from the Render dashboard, and set it as
   `ai020-dashboard`'s `BACKEND_URL` env var (Render's Blueprint
   templating can't reliably fill in a scheme-prefixed cross-service URL
   — see the comment in `render.yaml` — so this one variable is a
   manual one-time step). Redeploy `ai020-dashboard`.
4. Seed the curated demo dataset:
   ```bash
   # from the Render dashboard's Shell tab on ai020-backend, or via
   # `render ssh ai020-backend` with the Render CLI
   python scripts/generate_demo_dataset.py
   ```
5. Visit the dashboard's URL. Expect a ~30-60s cold start on the first
   request after idling (Render free tier spins services down after 15
   minutes of inactivity) — this is expected, not a bug, and worth
   mentioning up front if someone else is watching the demo live.

### Option B — Railway

1. Push to GitHub, then **New Project** → **Deploy from GitHub repo** in
   Railway, selecting this repo. Railway detects `railway.json` and
   builds from the existing `Dockerfile`.
2. Add a Postgres plugin (**New** → **Database** → **PostgreSQL**);
   Railway injects `DATABASE_URL` automatically into linked services —
   confirm it's linked to the backend service's variables.
3. Set the other env vars from `.env.example`'s list
   (`EMBEDDING_MODEL_NAME`, `MLFLOW_*`, `ALLOWED_ORIGINS`) in the
   service's Variables tab.
4. Deploy the dashboard as a second service the same way, pointing
   `BACKEND_URL` at the backend service's generated Railway domain.
5. Seed via Railway's **Shell** tab: `python scripts/generate_demo_dataset.py`.

### Option C — Fly.io

1. Install the `fly` CLI locally (outside this repo's containers) and
   `fly auth login`.
2. `fly launch --no-deploy` from the project root to let Fly adopt
   `fly.toml` (or deploy directly — it's already filled in).
3. Provision Postgres: `fly postgres create`, then attach it
   (`fly postgres attach <db-app-name>`) — this sets `DATABASE_URL` as a
   Fly secret automatically. Alternatively, point `DATABASE_URL` (via
   `fly secrets set`) at any external managed Postgres.
4. `fly deploy`.
5. Seed: `fly ssh console -C "python scripts/generate_demo_dataset.py"`.
6. `fly.toml` only configures the backend — see its header comment for
   why the dashboard isn't included and what the alternative is
   (`/docs` alone is enough to demo every engine without a dashboard at
   all, or run the dashboard on Render/Railway pointed at the Fly URL).

### Curated demo dataset

All three options above seed with `scripts/generate_demo_dataset.py`
(Day 18), not `scripts/generate_mock_data.py` (Day 2). The Day 2 script
produces a large, fully-random 120-intern dataset good for realistic-
scale testing; the Day 18 script is a small, hand-tuned 24-intern set
engineered so a demo walking through the grading rubric's example flows
doesn't have to go fishing for the right intern/team:

- A clean, single-clear-leader team and a competing-leadership team,
  side by side, so Day 16's `GET /team-chemistry/team/{id}` visibly
  shows the `leadership_balance` flag differ between the two.
- Two interns pre-marked unavailable, so `GET /rebalance/needed` has
  something to show immediately after `/recommend-teams` runs.
- Every intern has both a positive and a friction-leaning mentor
  comment, so the chemistry engine's `feedback_sentiment` signal has
  real language to react to.
- 4 projects with distinct required tech stacks, each matched by at
  least one intern's actual stack, so project matching reliably finds a
  fit to demo workload distribution against.

See the script's own docstring for the full design rationale.

### CORS for a hosted deployment

`ALLOWED_ORIGINS` (Day 17/18, `app/config.py`) defaults to `*`, which is
fine for a quick demo but should be set to the actual deployed
dashboard's origin once known, per the env var's comment in
`.env.example`.

## Common operations

**Tear down (keep data):**
```bash
docker compose down
```

**Tear down and wipe all data (Postgres, HF cache, MLflow runs):**
```bash
docker compose down -v
rm -rf mlruns
```

**Rebuild after a dependency change (`requirements.txt` / `dashboard/requirements.txt`):**
```bash
docker compose up --build
```

**Tail backend logs:**
```bash
docker compose logs -f backend
```

**Open a shell in the backend container** (e.g. to run one-off scripts or
inspect the venv):
```bash
docker compose exec backend bash
```

## Troubleshooting

- **`database: "error"` from `/health`, or backend can't connect on
  first boot.** The backend's `depends_on: db: condition: service_healthy`
  should prevent this, but if `db`'s healthcheck is slow (cold volume,
  underpowered host), wait a few seconds and retry. If it persists, check
  `docker compose logs db` for a Postgres startup error.
- **Alembic migration fails against an existing `pgdata` volume.** Usually
  means the volume predates a schema change from an earlier day. For a
  local dev instance where data loss is fine: `docker compose down -v`
  and start again from step 2.
- **First embedding call is slow / times out.** Expected on a genuinely
  first run — the model weights are downloading into `hf_cache`. Subsequent
  calls (and subsequent container restarts) reuse the cached volume and
  are fast. Check `docker compose logs backend` for
  `"Loading sentence-transformers model"` to confirm this is what's
  happening rather than a real error.
- **Dashboard shows connection errors to the API.** Confirm `BACKEND_URL`
  inside the `dashboard` service resolves — it's set to
  `http://backend:8000`, the Docker Compose service name, not `localhost`;
  this only matters if you've changed the compose network setup.
- **MLflow logging warnings in backend logs
  (`"MLflow tracking failed; continuing without it"`).** By design —
  see `app/ml/mlflow_tracking.py`. The API keeps serving
  `/success-probability` normally; check that `./mlruns` is writable by
  the container's user if you want tracking to actually record runs.
