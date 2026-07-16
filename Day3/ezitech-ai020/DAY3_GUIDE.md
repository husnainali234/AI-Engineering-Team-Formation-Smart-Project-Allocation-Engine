# Day 3 — Core CRUD & Ingestion: Full Walkthrough

Goal for today: **Swagger UI shows working CRUD + import endpoint tested against mock data.**
This builds on Day 2's frozen schema — no model changes, just an API surface on top of it.

---

## What's new since Day 2

```
ezitech-ai020/
├── app/
│   ├── schemas.py                  # NEW — Pydantic request/response contracts
│   ├── main.py                     # UPDATED — wires in the 4 new routers
│   └── routers/                    # NEW
│       ├── __init__.py
│       ├── interns.py              # CRUD for /interns
│       ├── projects.py             # CRUD for /projects
│       ├── teams.py                # CRUD for /teams + member add/remove
│       └── import_data.py          # /import — CSV/JSON portal-sync simulation
└── requirements.txt                # UPDATED — added python-multipart, email-validator
```

## 0. Drop in the files

Copy `app/schemas.py`, `app/routers/`, and the updated `app/main.py` and
`requirements.txt` from this package into your repo, overwriting the old
`app/main.py` and `requirements.txt`.

## 1. Rebuild the container (new dependencies)

```bash
docker compose up -d --build
docker compose ps
```

`python-multipart` is required for FastAPI to accept file uploads (`/import`),
and `email-validator` is required for Pydantic's `EmailStr` type used on
`Intern.email`. Both are new in Day 3's `requirements.txt` — this is why a
rebuild (not just a restart) is needed.

## 2. Open Swagger and look around

```
http://localhost:8000/docs
```

You should now see four new tag groups: **interns**, **projects**, **teams**,
**import** — each with the standard REST verbs, plus two extra routes under
**teams** for adding/removing a single member.

## 3. Exercise the CRUD endpoints against your Day 2 mock data

Your DB already has 120 interns and 15 projects seeded from Day 2, so you can
test reads immediately:

```bash
curl "http://localhost:8000/interns?limit=5"
curl "http://localhost:8000/interns?technology_stack=React&is_available=true"
curl "http://localhost:8000/projects?difficulty_level=Hard"
```

Then test writes. From Swagger (`/docs`) or curl:

```bash
# Create
curl -X POST http://localhost:8000/interns \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test Intern","email":"test.intern@example.com","technology_stack":"FastAPI, Docker"}'

# Update (partial — only fields you send change)
curl -X PUT http://localhost:8000/interns/121 \
  -H "Content-Type: application/json" \
  -d '{"leadership_score": 8.5}'

# Delete
curl -X DELETE http://localhost:8000/interns/121
```

Confirm the guardrails work as designed, not just the happy path:
- POST an intern with an email that already exists → expect `409`.
- DELETE a project that has a team assigned to it → expect `409` (teams must
  be reassigned or removed first; this mirrors the real constraint you'll
  hit once Team Formation starts writing teams on Day 7).
- POST the same `intern_id` to a team's `/members` twice → expect `409` on
  the second call.

## 4. Build a team end-to-end

This exercises the one non-trivial write path — creating a team with members
in a single call, and the two supporting member-management routes:

```bash
# Create a team with two existing interns already attached
curl -X POST http://localhost:8000/teams \
  -H "Content-Type: application/json" \
  -d '{"name":"Team Falcon","project_id":1,"member_ids":[1,2]}'

# Add a third member afterward
curl -X POST http://localhost:8000/teams/1/members \
  -H "Content-Type: application/json" \
  -d '{"intern_id": 3, "role": "Member"}'

# Remove one
curl -X DELETE http://localhost:8000/teams/1/members/3

# Confirm the final roster
curl http://localhost:8000/teams/1
```

## 5. Test the /import endpoint (the real deliverable for today)

This is the piece that simulates the case study's "integrate directly with
the Ezitech Internship Portal" requirement. It accepts a CSV or JSON file and
upserts `Intern` rows **by email** — same email updates the existing intern,
new email creates one.

**Test with your own Day 2 seed file** — this alone proves the endpoint
round-trips real data:

```bash
curl -X POST http://localhost:8000/import \
  -F "file=@data/interns_seed.csv"
```

Expected response shape:

```json
{
  "source_format": "csv",
  "rows_received": 120,
  "interns_created": 0,
  "interns_updated": 120,
  "rows_skipped": 0,
  "errors": []
}
```

(`interns_updated: 120` because these emails already exist from Day 2's seed
— that's the upsert working correctly, not a bug.)

**Test the JSON path and the error-handling path** too, since a real portal
export will have some bad rows in it:

```bash
cat > /tmp/sample.json << 'EOF'
[
  {"full_name": "Zara Iqbal", "email": "zara.iqbal@example.com", "technology_stack": "Vue.js", "leadership_score": 7.0},
  {"full_name": "Bad Row", "email": "not-an-email"}
]
EOF

curl -X POST http://localhost:8000/import -F "file=@/tmp/sample.json"
```

Expect `interns_created: 1`, `rows_skipped: 1`, and a readable validation
error in `errors` for the bad row — the import should never fail outright
just because one row is malformed.

## 6. Verify in the database directly

```bash
docker compose exec db psql -U ezitech -d ezitech_ai020 -c "SELECT count(*) FROM interns;"
docker compose exec db psql -U ezitech -d ezitech_ai020 -c "SELECT full_name, email, leadership_score FROM interns WHERE email = 'zara.iqbal@example.com';"
```

## 7. Commit

```bash
git add .
git commit -m "Day 3: CRUD endpoints for interns/projects/teams + /import endpoint (CSV/JSON upsert)"
git push
```

## Design notes worth knowing before Day 4

- **Why upsert by email, not id**: a real portal re-sync won't know your
  internal auto-increment ids. Email is the natural external key, which is
  also why `Intern.email` is `unique=True` in the Day 1/2 schema.
- **Why `/import` never hard-fails on one bad row**: a 120-row export failing
  entirely because row 47 has a typo is a bad ingestion design. Collecting
  errors and reporting `rows_skipped` is what a production sync job does.
- **Why `TeamCreate` takes `member_ids` instead of requiring two calls**:
  Day 7's Team Formation Engine will call this same endpoint programmatically
  once per cluster it produces — it needs to create a team with its members
  in one atomic call, not team-then-members-then-hope-nothing-fails-between.
- **`schemas.py` has no nested `Intern.skills` field yet.** That's deliberate
  — Day 4 adds the Skill Matrix aggregation logic, and that's when it'll be
  clear whether skills should nest inline or stay a separate lookup endpoint.

## End-of-Day 3 Checklist

- [ ] Container rebuilt with `python-multipart` + `email-validator`
- [ ] `/docs` shows interns, projects, teams, import route groups
- [ ] Full CRUD (create/read/update/delete) tested for interns and projects
- [ ] Team creation with `member_ids`, plus add/remove member, tested
- [ ] 409 guardrails confirmed (duplicate email, duplicate team member, delete project with teams)
- [ ] `/import` tested against `data/interns_seed.csv` — upsert confirmed via row counts
- [ ] `/import` tested with a JSON file containing one intentionally bad row — confirmed it's skipped, not fatal
- [ ] Everything committed and pushed

If all boxes are checked, you're on schedule for Day 4 (Sentence-Transformers
embeddings pipeline for intern skills/interests, plus the Skill Matrix
aggregation logic — both engineers building directly on today's `/interns`
data and CRUD layer).
