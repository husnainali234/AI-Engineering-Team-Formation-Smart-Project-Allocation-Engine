# Day 6 — Skill Matching + Compatibility: Full Walkthrough

Goal for today: **ranked teammate recommendations from embedding similarity,
a complementary-skills variant, a team skill-diversity score, and a weighted
Compatibility Score with a full explainable breakdown.** Built entirely on
top of Day 4's embeddings and skill data plus fields Day 1-2 already put on
`Intern`/`TeamHistory` — no schema changes today.

---

## What's new since Day 5

```
ezitech-ai020/
├── app/
│   ├── services/
│   │   ├── matching_service.py         # NEW — cosine similarity, ranking, diversity
│   │   └── compatibility_service.py    # NEW — weighted compatibility score
│   ├── schemas.py                      # UPDATED — matching/compatibility/recommendation schemas
│   ├── main.py                         # UPDATED — wires in 3 new routers
│   └── routers/
│       ├── matching.py                 # NEW — /matching/*
│       ├── compatibility.py            # NEW — /compatibility/*
│       └── recommendations.py          # NEW — /recommendations/* (matching + compatibility blended)
└── tests/
    ├── test_matching_service.py        # NEW
    ├── test_compatibility_service.py   # NEW
    ├── test_router_matching.py         # NEW
    ├── test_router_compatibility.py    # NEW
    └── test_router_recommendations.py  # NEW
```

## 1. Skill Matching Engine

Ranks candidates by **cosine similarity** of their Day 4 sentence-transformer
embeddings — same overall skill/interest profile as the target intern:

```bash
curl "http://localhost:8000/matching/interns/1/recommendations?limit=5"
```

```json
[
  {"intern_id": 42, "full_name": "...", "similarity_score": 0.83, "diversity_score": 0.62},
  ...
]
```

**Complementary matching** inverts the ranking — highest `diversity_score`
(least skill overlap) among candidates still similar enough (`min_similarity`,
default `0.3`) to be in a related problem domain:

```bash
curl "http://localhost:8000/matching/interns/1/complementary?min_similarity=0.3&limit=5"
```

**Team skill diversity** — one number, 0.0 (fully redundant skills) to 1.0
(no overlap at all), for an existing team:

```bash
curl http://localhost:8000/matching/teams/1/diversity
```

Both endpoints return `409` if the target intern has no embedding yet
(`POST /embeddings/interns/{id}/generate` first) — matching against a
non-existent vector isn't a `404` (the intern exists) or a silent empty
result, it's a distinct, actionable error.

## 2. Compatibility Score

A weighted combination of six signals, each normalized to 0.0-1.0 before
weighting (weights defined in `compatibility_service.COMPATIBILITY_WEIGHTS`,
sum to 1.0):

| Signal | Weight | Source |
|---|---|---|
| Communication | 0.20 | `Intern.communication_score` |
| Leadership | 0.15 | `Intern.leadership_score` |
| Attendance | 0.15 | `Intern.attendance_pct` |
| Team history | 0.15 | `TeamHistory.outcome_rating` for shared past teams |
| Skill diversity | 0.20 | Day 6 matching engine's diversity score |
| GitHub activity | 0.15 | `Intern.github_contributions` (saturates at 200) |

```bash
curl "http://localhost:8000/compatibility/pair?intern_a_id=1&intern_b_id=2"
```

```json
{
  "intern_a_id": 1, "intern_b_id": 2, "total_score": 71.4,
  "components": {
    "communication": {"raw_score": 0.72, "weight": 0.2, "contribution": 0.144},
    "...": "..."
  }
}
```

Every component is returned, not just the total — the score is explainable,
not a black box.

**Team-level**: average pairwise compatibility across every member pair:

```bash
curl http://localhost:8000/compatibility/team/1
```

To actually persist that average onto `Team.compatibility_score` (the field
Day 1's ERD reserved for this — "0-100, from Collaboration Prediction
Model"):

```bash
curl -X POST http://localhost:8000/compatibility/team/1/recalculate
curl http://localhost:8000/teams/1   # compatibility_score now populated
```

`GET /compatibility/team/{id}` stays read-only/side-effect-free on purpose —
only the explicit `/recalculate` action writes back to the team row.

## 3. Recommendation API

Distinct from both of the above: **who should this intern actually team up
with**, blending embedding similarity (40%) with compatibility score (60%)
into one ranked list:

```bash
curl http://localhost:8000/recommendations/interns/1
```

```json
[
  {
    "intern_id": 42, "full_name": "...", "similarity_score": 0.71,
    "diversity_score": 0.55, "compatibility_score": 82.3, "blended_rank_score": 0.778
  }
]
```

This is the endpoint a "suggest a teammate for this intern" UI feature would
actually call — `/matching` and `/compatibility` are the two engines it's
built from, each independently useful (and independently testable) on their
own.

## 4. Run the test suite

```bash
docker compose exec backend pytest tests/ -v
```

`test_matching_service.py` / `test_compatibility_service.py` unit-test the
scoring logic directly (cosine similarity edge cases, diversity formula,
weight normalization). `test_router_matching.py` /
`test_router_compatibility.py` / `test_router_recommendations.py`
integration-test the endpoints, including the `404`/`409`/`422` error paths.

## 5. Commit

```bash
git add .
git commit -m "Day 6: Skill Matching Engine (cosine similarity + complementary + diversity) and weighted Compatibility Score"
git push
```

## Design notes worth knowing

- **Why skill diversity is `|union| / (|A|+|B|)`, not Jaccard**: Jaccard
  (`|intersection|/|union|`) scores *identical* skill sets as `1.0` — the
  opposite of what "diversity" should mean for team formation. This formula
  instead gives identical sets `0.5` (fully redundant) and disjoint sets
  `1.0` (maximally complementary) — see `app/services/skill_utils.py`.
- **Why the soft-skill components reward similarity, not just magnitude**:
  two solid-but-average communicators are treated as more compatible on that
  axis than one excellent and one poor communicator, even if the raw average
  is the same — `compatibility_service._soft_skill_component`.
- **Why team history defaults to neutral (0.5), not 0.0, with no shared
  past team**: absence of a shared-history record isn't evidence of poor
  compatibility, just missing data — scoring it as a penalty would unfairly
  punish interns who've simply never overlapped before.
- **Why GitHub activity saturates at 200 contributions**: without a cap, one
  prolific outlier would dominate that component's contribution for every
  pair they're in, which isn't a meaningful compatibility signal beyond a
  reasonable "actively contributing" threshold.

## End-of-Day 6 Checklist

- [ ] `/matching/interns/{id}/recommendations` returns similarity-ranked candidates
- [ ] `/matching/interns/{id}/complementary` returns diversity-ranked candidates, respecting `min_similarity`
- [ ] `/matching/teams/{id}/diversity` returns a 0.0-1.0 score
- [ ] `/compatibility/pair` returns a full 6-component breakdown summing correctly to `total_score`
- [ ] `/compatibility/team/{id}/recalculate` persists to `Team.compatibility_score`
- [ ] `/recommendations/interns/{id}` returns a blended, ranked list
- [ ] `pytest tests/` (full Day 1-6 suite) passes
- [ ] Everything committed and pushed

If all boxes are checked, Week 1's engine work (embeddings, skill matrix,
matching, compatibility) is complete and integration-tested end to end —
ready for Week 2's Team Formation Engine to consume all of it.
