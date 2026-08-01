# Day 4 — Embeddings & Skill Matrix: Full Walkthrough

Goal for today: **every intern has a sentence-transformer embedding of their
skill/interest profile, generated automatically and cached; the Skill Matrix
endpoints return real technology-frequency and proficiency numbers.**
This builds directly on Day 3's `/interns` CRUD and `/import` endpoint — no
existing routes changed shape, this is a new layer on top.

---

## What's new since Day 3

```
ezitech-ai020/
├── app/
│   ├── models.py                       # UPDATED — 3 new columns on Intern
│   ├── schemas.py                      # UPDATED — embedding + skill-matrix schemas
│   ├── main.py                         # UPDATED — wires in 2 new routers
│   ├── ml/                             # NEW
│   │   ├── __init__.py
│   │   └── embedding_model.py          # lazy-loaded SentenceTransformer singleton
│   ├── repositories/                   # NEW — Day 4-6 shared data access
│   │   ├── __init__.py
│   │   ├── intern_repository.py
│   │   └── team_repository.py
│   ├── services/                       # NEW — Day 4-6 business logic
│   │   ├── __init__.py
│   │   ├── skill_utils.py              # shared skill-set helpers
│   │   ├── embedding_service.py        # text-building, hashing/caching, generation
│   │   └── skill_matrix_service.py     # frequency + proficiency aggregation
│   └── routers/
│       ├── embeddings.py               # NEW — /embeddings/*
│       ├── skill_matrix.py             # NEW — /skill-matrix/*
│       └── interns.py                  # UPDATED — auto-generates embedding on create/update
├── alembic/versions/
│   └── 0002_add_intern_embedding_columns.py   # NEW
└── requirements.txt                    # UPDATED — sentence-transformers, numpy, pytest, httpx
```

## 0. Rebuild and migrate

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

The rebuild is required because `sentence-transformers` (and its `torch`
dependency) is new in `requirements.txt` — this is a real download, budget a
few minutes on first build. The migration adds three nullable columns to
`interns` (`skill_embedding`, `embedding_updated_at`, `embedding_source_hash`)
— nothing existing changes shape, so this is safe to run against your
already-seeded Day 2/3 data.

## 1. How the embedding pipeline works

Each intern's profile — `technology_stack`, structured skills (name +
proficiency, from `InternSkill`), and `project_interests` — is composed into
a short natural-language description (`embedding_service.build_intern_text`),
then embedded with `all-MiniLM-L6-v2` (384 dimensions) via
`sentence-transformers`. The result is stored directly on `Intern.skill_embedding`
as JSON — deliberately not a Postgres-only `ARRAY`/`vector` column, so the
same schema works against SQLite in tests without needing the `pgvector`
extension installed.

**Caching**: the SHA-256 of the exact text embedded is stored in
`embedding_source_hash`. Re-running generation on an intern whose profile
hasn't changed is a no-op — the (relatively expensive) model call is skipped
entirely. This matters once you're re-importing 100+ rows regularly.

**Automatic generation**: `POST /interns` and `PUT /interns/{id}` both
trigger regeneration after the write commits — best-effort, wrapped so a
model/network hiccup never fails the CRUD call itself. Same for `/import` at
the batch level (see Day 5).

## 2. Generate embeddings for your existing Day 2/3 seed data

Data seeded before today has no embedding yet — backfill it once:

```bash
curl -X POST http://localhost:8000/embeddings/generate-all
```

```json
{"total": 120, "generated": 120, "skipped_cached": 0, "errors": []}
```

Run it again immediately and confirm caching works — this time everything
should be `skipped_cached`, not `generated`:

```bash
curl -X POST http://localhost:8000/embeddings/generate-all
# {"total": 120, "generated": 0, "skipped_cached": 120, "errors": []}
```

## 3. Inspect a single intern's embedding

```bash
curl http://localhost:8000/embeddings/interns/1
```

```json
{"intern_id": 1, "dimensions": 384, "embedding": [0.0123, -0.0456, ...], "embedding_updated_at": "2026-07-17T10:00:00"}
```

Update that intern's tech stack and confirm the hash-based cache correctly
detects the change and regenerates:

```bash
curl -X PUT http://localhost:8000/interns/1 -H "Content-Type: application/json" -d '{"technology_stack": "Rust, WebAssembly"}'
curl http://localhost:8000/embeddings/status | python -m json.tool | head -20
```

## 4. Exercise the Skill Matrix endpoints

```bash
# Org-wide technology frequency
curl http://localhost:8000/skill-matrix/technology-frequency

# Org-wide proficiency aggregation (avg/min/max per skill, structured InternSkill rows only)
curl http://localhost:8000/skill-matrix/proficiency-aggregation

# Full per-team matrix (frequency + proficiency + which interns hold each skill)
curl http://localhost:8000/skill-matrix/team/1
```

Both `technology-frequency` and `proficiency-aggregation` also accept
`?team_id=` to scope to one team instead of the whole org.

## 5. Run the new test suite

```bash
docker compose exec backend pytest tests/ -v
```

Tests run against an in-memory SQLite DB with a deterministic fake embedding
model (see `tests/conftest.py`) — no network access or real model download
needed to run them, which is also why CI can run this suite without a GPU or
internet access.

## 6. Commit

```bash
git add .
git commit -m "Day 4: Sentence-Transformers embedding pipeline + Skill Matrix (frequency/proficiency aggregation)"
git push
```

## Design notes worth knowing before Day 5

- **Why both `InternSkill` and `technology_stack` feed the skill matrix**:
  `/import` (Day 3) only ever populates the free-text `technology_stack`
  field, not structured `InternSkill` rows. Using only `InternSkill` as the
  skill source would make the Skill Matrix return near-empty results for
  anything that came in through `/import` — which fails the Day 5 checkpoint.
  `app/services/skill_utils.py` documents this in detail.
- **Why the embedding model import is lazy**: `sentence-transformers` pulls
  in `torch`, which is slow to import and unnecessary for the 90% of
  requests that are plain CRUD. `app/ml/embedding_model.py` only imports it
  inside `get_model()`, on first actual use.
- **Why embedding generation never raises out of the CRUD routers**: an ML
  dependency being temporarily unavailable (cold start, no network yet)
  should never turn into a `500` on `POST /interns`. Worst case, the intern
  is created without an embedding and picked up by the next
  `POST /embeddings/generate-all`.

## End-of-Day 4 Checklist

- [ ] Container rebuilt with `sentence-transformers` + `numpy`
- [ ] `alembic upgrade head` applied the new embedding columns
- [ ] `POST /embeddings/generate-all` backfilled all existing interns
- [ ] Re-running `generate-all` shows `skipped_cached` for everyone (caching confirmed)
- [ ] Updating an intern's tech stack via `PUT /interns/{id}` triggers regeneration
- [ ] `/skill-matrix/technology-frequency`, `/proficiency-aggregation`, and `/team/{id}` all return real numbers
- [ ] `pytest tests/` passes
- [ ] Everything committed and pushed

If all boxes are checked, you're on schedule for Day 5 (Checkpoint 1 —
proving Import → DB → Embedding → Skill Matrix works as one integrated
pipeline, not four separately-tested pieces).
