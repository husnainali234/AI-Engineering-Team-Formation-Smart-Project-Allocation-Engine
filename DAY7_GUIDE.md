# Day 7 — Team Formation + Leadership: Full Walkthrough

Goal for today: **an engine that takes N available interns and outputs
balanced candidate teams — not skill-identical clusters — each with a
suggested leader, explainable end to end.** This is the execution guide's
own "hardest ML day" (called out explicitly in section 5: "most likely
Day 7, 9, or 11"), so today's walkthrough spends more time on *why* than
usual.

---

## What's new since Day 6

```
ezitech-ai020/
├── app/
│   ├── services/
│   │   ├── team_formation_service.py   # NEW — KMeans/Agglomerative clustering + round-robin team assembly
│   │   └── leadership_service.py       # NEW — hybrid rule-based leadership scoring
│   ├── repositories/
│   │   └── intern_repository.py        # UPDATED — list_available_unassigned_with_embeddings()
│   ├── schemas.py                      # UPDATED — leadership/team-formation schemas
│   ├── main.py                         # UPDATED — wires in 2 new routers
│   └── routers/
│       ├── leadership.py               # NEW — /leadership/*
│       └── team_formation.py           # NEW — /team-formation/*
├── requirements.txt                    # UPDATED — scikit-learn, scipy
└── tests/
    ├── test_leadership_service.py      # NEW
    ├── test_team_formation_service.py  # NEW
    ├── test_router_leadership.py       # NEW
    └── test_router_team_formation.py   # NEW
```

## 1. Why clustering alone doesn't give you "balanced" teams

KMeans/Agglomerative clustering on embeddings groups *similar* people
together — that's the whole point of clustering. But the spec explicitly
wants teams that **aren't skill-identical**. Naively treating "one cluster
= one team" gets you the opposite of what's asked: a team of four React
developers who all look alike on paper.

So today's engine uses clustering to find **skill archetypes** across the
*whole* candidate pool (one archetype per seat in a team — `min(team_size,
candidate_count)` clusters), then builds each team by drawing **one member
per archetype, round-robin, across all teams simultaneously**. The result:
every team gets a spread of different skill archetypes instead of a pile of
near-duplicates. This is the load-bearing design decision for the whole
day — see `app/services/team_formation_service.py`'s module docstring for
the full reasoning.

```bash
curl -X POST http://localhost:8000/team-formation/preview \
  -H "Content-Type: application/json" \
  -d '{"team_size": 4, "algorithm": "kmeans"}'
```

```json
{
  "algorithm": "kmeans",
  "archetype_count": 4,
  "teams": [
    {
      "team_index": 0,
      "members": [
        {"intern_id": 3, "full_name": "...", "role": "Lead", "skill_archetype": 2},
        {"intern_id": 7, "full_name": "...", "role": "Member", "skill_archetype": 0}
      ],
      "suggested_leader_intern_id": 3,
      "suggested_leader_name": "...",
      "diversity_score": 0.81
    }
  ],
  "unassigned_intern_ids": [14]
}
```

Two knobs, both optional in the request body:
- `intern_ids` — explicit candidate pool. Omit it and the engine defaults to
  `InternRepository.list_available_unassigned_with_embeddings()`: interns
  with an embedding, marked available, **and not already on a team** — so
  re-running formation never double-books someone.
- `algorithm` — `"kmeans"` (default) or `"agglomerative"`.

If the candidate count doesn't divide evenly into `team_size`-sized teams,
the remainder comes back as `unassigned_intern_ids` rather than getting
crammed into an oversized team or forced into an undersized one.

## 2. Leadership Detection

A separate, independently useful engine — same explainable-breakdown shape
as Day 6's Compatibility Score:

| Signal | Weight | Source |
|---|---|---|
| Leadership score | 0.40 | `Intern.leadership_score` |
| Communication | 0.20 | `Intern.communication_score` |
| Team history | 0.15 | `TeamHistory.outcome_rating`, this intern's own past teams |
| Contribution consistency | 0.25 | 0.6 × attendance + 0.4 × GitHub activity (saturating early) |

```bash
curl http://localhost:8000/leadership/interns/3/score
```

The "hybrid rule + ML" the spec asks for describes the *system*, not just
this module in isolation: this rule-based scorer picks a leader **within**
a group; the groups themselves come from Day 7's clustering engine. Rules
decide "who leads", ML decides "who's on the team together" — that split is
the hybrid. A well-explained weighted rule also beats a black-box
classifier here for a more concrete reason: there's no labeled "was
actually a good leader" outcome data yet to train one on.

```bash
curl http://localhost:8000/leadership/team/1/suggest
```

Returns the full ranking (every member scored, sorted, ties broken by
intern id) plus which one the engine suggests. Read-only — like Day 6's
`GET /compatibility/team/{id}`, it doesn't write anything. To actually set
`TeamMember.role`:

```bash
curl -X POST http://localhost:8000/leadership/team/1/apply
```

Sets the top-ranked member's role to `"Lead"`, everyone else to `"Member"`.

## 3. Committing formed teams to the database

`/team-formation/preview` never writes to the DB — it's a dry run. To
actually create the `Team` + `TeamMember` rows (role `"Lead"` for the
suggested leader):

```bash
curl -X POST http://localhost:8000/team-formation/commit \
  -H "Content-Type: application/json" \
  -d '{"team_size": 4}'
```

```json
{
  "algorithm": "kmeans",
  "archetype_count": 4,
  "teams": [ { "id": 5, "name": "Auto-Formed Team 1", "members": [...] } ],
  "unassigned_intern_ids": [14]
}
```

`teams` here is real `TeamOut` objects (same shape `GET /teams/{id}`
returns) — these are now persisted rows any other Day 1-6 endpoint can see.

## 4. Run the test suite

```bash
docker compose exec backend pytest tests/ -v
```

`test_team_formation_service.py` covers the clustering + round-robin logic
directly: missing-embedding errors, the too-few-candidates guard, unknown
algorithms, even assignment when candidates divide evenly, remainder
handling when they don't, and determinism (same input → same teams, twice
in a row). `test_leadership_service.py` covers the weighted scoring
(weights sum to 1.0, neutral-default team history, ranking order,
tie-breaking). The two router test files integration-test the HTTP layer,
including the 404/409/422 paths.

## 5. Commit

```bash
git add .
git commit -m "Day 7: Team Formation Engine (KMeans/Agglomerative + balanced round-robin) and hybrid Leadership Detection"
git push
```

## Design notes worth knowing

- **Why `archetype_count = min(team_size, candidate_count)`, not something
  tied to `num_teams`**: archetypes represent "seats" — the goal is one
  different skill type per team, not one cluster per team. Tying archetype
  count to team size is what makes the round-robin assembly produce diverse
  teams regardless of how many teams end up being formed.
- **Why round-robin, not a bin-packing optimizer**: a real bin-packing
  solution (minimize intra-team similarity variance, say) is more
  "optimal" but much harder to explain to a mentor reading the output —
  and per the execution guide's own advice, a simple, explainable approach
  beats a complex unexplained one on the Explainability criterion. The
  round-robin assignment is one paragraph to describe and fully
  deterministic.
- **Why leader suggestion is a separate service from team formation, not
  baked into the clustering loop**: `leadership_service` is independently
  useful — `/leadership/team/{id}/suggest` works on *any* existing team,
  including ones built manually via Day 3's `POST /teams`, not just
  auto-formed ones. Keeping it separate (the same "engines are independently
  useful and independently testable" principle from Day 6) means Day 9's
  Risk Analysis module can also call it directly if a team's suggested
  leader ever needs re-evaluating.
- **Why `list_available_unassigned_with_embeddings` excludes already-teamed
  interns by default, unlike Day 6's `list_with_embeddings`**: 1-to-1
  teammate matching (Day 6) doesn't care if a candidate is already on a
  team — the recommendation is informational. Team *formation* actually
  creates commitments, so silently double-booking someone already on
  another team would be a real bug, not just a stale suggestion.

## End-of-Day 7 Checklist

- [ ] `POST /team-formation/preview` returns candidate teams with a
      `diversity_score` per team and never writes to the DB
- [ ] `POST /team-formation/commit` persists real `Team`/`TeamMember` rows,
      leader role set to `"Lead"`
- [ ] Remainder interns that don't divide evenly come back in
      `unassigned_intern_ids`, not forced into a team
- [ ] `GET /leadership/interns/{id}/score` returns a 4-component
      breakdown summing correctly to `total_score`
- [ ] `GET /leadership/team/{id}/suggest` / `POST .../apply` both work,
      the POST actually sets `TeamMember.role`
- [ ] `pytest tests/` (full Day 1-7 suite) passes
- [ ] Everything committed and pushed

If all boxes are checked, given N interns the engine now outputs candidate
teams plus a suggested leader per team — today's end-of-day deliverable —
and Day 8 has real, persisted teams to recommend projects for.
