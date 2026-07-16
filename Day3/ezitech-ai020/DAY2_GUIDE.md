# Day 2 — Database Layer: Full Walkthrough

Goal for today: **DB migrated; seed script produces a realistic mock dataset (CSV + DB rows).**
This builds directly on your Day 1 `app/models.py` — no schema changes were made, it was
just turned into real, versioned migrations, then filled with data.

---

## What's new since Day 1

```
ezitech-ai020/
├── alembic.ini                        # NEW — Alembic config
├── alembic/                           # NEW
│   ├── env.py                         # wired to app.database.Base + DATABASE_URL
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py     # creates all 9 tables from Day 1's ERD
├── scripts/                           # NEW
│   ├── generate_mock_data.py          # Faker seed script
│   └── day2_setup.sh                  # one-command: build -> migrate -> seed
├── data/
│   └── interns_seed.csv               # generated when you run the seed script
├── Dockerfile                         # updated: also copies alembic/ + scripts/
├── docker-compose.yml                 # updated: also mounts alembic/, scripts/, data/
└── requirements.txt                   # updated: added Faker
```

## 0. Fastest path — run everything with one command

```bash
bash scripts/day2_setup.sh
```

This builds the containers, waits for Postgres and the API to be ready, runs
`alembic upgrade head`, then runs the seed script. On Windows, run it from Git Bash
or WSL (native Command Prompt/PowerShell can't run `.sh` files directly).

If you'd rather run each step yourself (or something in the one-liner fails and you
want to see exactly where), the manual steps are below — they're what the script
does under the hood.

---

## 1. Bring the stack up

```bash
docker compose up -d --build
```

`-d` runs it in the background so you can run the next commands in the same terminal.
Confirm both containers are healthy:

```bash
docker compose ps
```

## 2. Run the Alembic migration

```bash
docker compose exec backend alembic upgrade head
```

This creates all 9 tables from Day 1's ERD (`interns`, `skills`, `intern_skills`,
`projects`, `teams`, `team_members`, `team_history`, `mentor_feedback`, `attendance`)
exactly as defined in `app/models.py` — no drift between the ORM and the real DB.

Verify:

```bash
docker compose exec db psql -U ezitech -d ezitech_ai020 -c "\dt"
```

You should see all 9 tables listed.

**This is the schema-freeze point.** From here, changing a column cascades into every
engine and dashboard built in Weeks 2-3 — if you need to tweak something, do it now
rather than after Day 3.

## 3. Run the seed script

```bash
docker compose exec backend python scripts/generate_mock_data.py
```

What it generates, matching the exact functional-requirements list from Day 1:

| Table | Rows | Notes |
|---|---|---|
| `interns` | 120 | name, email, tech stack, GitHub URL + contribution count, case-study score, credits, attendance %, leadership/communication scores, availability, project interests |
| `skills` | 18 | pooled across Language / Framework / Tool / Domain categories |
| `intern_skills` | ~4-8 per intern | links interns to skills with a 1-5 proficiency |
| `projects` | 15 | title, description, required tech stack, difficulty |
| `attendance` | 30 days × 120 interns | daily present/absent, weighted by each intern's `attendance_pct` so the aggregate stays consistent with the detail |
| `mentor_feedback` | 2 per intern | mentor name, score, comment, date |
| `team_history` | ~half of interns | simulates some interns having been on a team in a previous batch — the "previous team history" signal Day 1's requirements call for |

`teams` and `team_members` are left empty — those get populated by the Team Formation
Engine starting Day 7, not seeded synthetically.

The script is **safe to re-run**: it clears its own tables first, so you can regenerate
fresh mock data any time without duplicate rows.

It also writes `data/interns_seed.csv` (visible on your host machine too, since that
folder is now mounted into the container).

## 4. Verify

```bash
docker compose exec db psql -U ezitech -d ezitech_ai020 -c "SELECT count(*) FROM interns;"
docker compose exec db psql -U ezitech -d ezitech_ai020 -c "SELECT full_name, technology_stack, attendance_pct FROM interns LIMIT 5;"
```

Open `data/interns_seed.csv` on your host and confirm it looks realistic.

## 5. Commit

```bash
git add .
git commit -m "Day 2: Alembic migrations for full schema + Faker seed script (120 interns)"
git push
```

## End-of-Day 2 Checklist

- [ ] `alembic upgrade head` ran with no errors, all 9 tables exist
- [ ] Schema reviewed and treated as frozen going forward
- [ ] `generate_mock_data.py` ran cleanly — 120 interns, 18 skills, 15 projects, attendance + feedback + team history seeded
- [ ] `data/interns_seed.csv` exists and looks realistic
- [ ] Row counts spot-checked via psql
- [ ] Everything committed and pushed

If all boxes are checked, you're on schedule for Day 3 (CRUD endpoints for
interns/projects/teams, plus the `/import` endpoint that will simulate the real
Ezitech Internship Portal integration on top of this same schema).
