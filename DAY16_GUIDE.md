# Day 16 — Bonus Features

## Goal

Per the execution guide: **"Implement Automatic Team Rebalancing (re-run
engine when a member becomes unavailable) or Conflict Risk Prediction"**
(Engineer A) and **"Implement Team Chemistry Prediction or
Cross-Technology Team Suggestions"** (Engineer B). Deliverable: two bonus
features, implemented and demoable. This guide covers the pair the
grading rubric's own Innovation criterion names as the example —
**Automatic Team Rebalancing** and **Team Chemistry Prediction**.

No new tables — both features reuse Day 1's ERD end to end.

## What's new since Day 15

```
ezitech-ai020/
├── app/
│   ├── services/
│   │   ├── team_rebalancing_service.py    # NEW — find/plan a member swap
│   │   └── team_chemistry_service.py      # NEW — team-level chemistry score
│   ├── repositories/
│   │   └── team_repository.py             # UPDATED — list_all_with_members_and_interns(), delete_member()
│   └── routers/
│       ├── team_rebalancing.py            # NEW — /rebalance/*
│       └── team_chemistry.py              # NEW — /team-chemistry/*
└── tests/
    ├── test_team_rebalancing_service.py   # NEW
    ├── test_team_chemistry_service.py     # NEW
    ├── test_router_rebalance.py           # NEW
    └── test_router_team_chemistry.py      # NEW
```

## 1. Automatic Team Rebalancing (Engineer A)

**`GET /rebalance/needed`** — every team with at least one member whose
`Intern.is_available` is `False`. Deliberately a reviewable list rather
than an automatic, silent side-effect of `PUT /interns/{id}`: swapping a
real person off a team is consequential enough that a mentor should see
who's being proposed as the replacement before it happens, not discover
it after the fact.

**`POST /rebalance/team/{id}`** — for every currently-unavailable member
on the team:

1. **Find the best-fit replacement** — highest skill-embedding cosine
   similarity to the departing member, among available, unassigned,
   embedded candidates (`team_rebalancing_service.find_replacement`,
   reusing Day 6's `matching_service.cosine_similarity`). Minimizes
   disruption to whatever the team was actually assembled for, rather
   than picking arbitrarily. Two members leaving at once get two
   *different* replacements — `plan_rebalance` removes each chosen
   candidate from the pool before considering the next departure.
2. **Swap the membership** — delete the departing `TeamMember` row, add
   one for the replacement. A departing member with no available
   replacement is left on the team rather than removed outright:
   dropping them without a replacement would trade "unavailable member
   still listed" for the worse problem of "team silently down a person",
   and the team stays flagged by `GET /rebalance/needed` until a
   candidate exists.
3. **Re-suggest a leader, if needed** — if the departing member held
   `role="Lead"` and a replacement was found, Day 7's
   `leadership_service.suggest_leader` re-ranks the new membership and
   reassigns the role. A lead departing with no replacement leaves the
   role in place, same reasoning as step 2.
4. **Rescore the team** — reuses `recommend_teams_service
   .compute_team_recommendation` (Day 10) against the new membership,
   the exact function `/recommend-teams` uses for a freshly-formed team.
   Deliberate reuse rather than a second scoring path: a rebalanced team
   is scored exactly the same way a new one would be, so nothing about
   compatibility, project fit, success probability, or risk can drift
   between the two flows. Workload is redistributed the same way
   `/recommend-teams` does, if a project is (still) matched.

Errors: `404` if the team doesn't exist; `409` if the team currently has
no unavailable members — calling this against a healthy team is a clear
error, not a silent no-op.

## 2. Team Chemistry Prediction (Engineer B)

**`GET /team-chemistry/team/{id}`** — a team-level interpersonal-friction
signal, deliberately distinct from two engines that might look like they
already cover this:

- **Day 6's Compatibility Score** averages six *pairwise* signals across
  every member pair. It can't see team-level structural effects — two
  members who both score a strong 8/10 on leadership actually score
  *well* on compatibility's pairwise leadership component (which rewards
  similarity between the pair, not closeness to an ideal team-wide
  count), even though two co-equal strong leaders is a classic real-world
  friction pattern.
- **Day 9's Success Probability** predicts project *outcome* from
  attendance/feedback/skill-balance — a performance forecast, not an
  interpersonal one.

Chemistry instead scores four team-level signals, weighted to sum to 1.0:

| Signal | Weight | What it measures |
|---|---|---|
| `leadership_balance` | 0.30 | Peaks at exactly one strong leader (`leadership_score >= 7.0`); zero is a mild risk, two or more is a steeper "competing ownership" risk |
| `shared_interests` | 0.20 | Average pairwise Jaccard similarity of `Intern.project_interests` — a field that's existed since Day 1 but until now was only ever folded into the Day 4 embedding text, never read as a discrete signal |
| `communication_spread` | 0.25 | Population stdev of `communication_score` across the *whole* team (not pairwise-averaged) — a tight cluster of similar communicators has less friction surface than a wide spread |
| `feedback_sentiment` | 0.25 | A small, transparent keyword scan over `MentorFeedback.comments` — free text that's existed since Day 1 but that no engine has read; `MentorFeedback.score` feeds Day 9, `.comments` never has |

Same explainable shape Day 6/7 already established: every component
returns `{raw_score, weight, contribution}`, plus a short list of
plain-English flags a mentor can act on (e.g. *"2 strong leaders on this
team — assign explicit ownership boundaries up front"*). Recomputed live
on every call — like Day 11's explanation, deliberately never persisted,
so it can't go stale relative to the team's current membership or the
latest mentor feedback on record.

`feedback_sentiment` is explicitly a rule-based heuristic, not a trained
sentiment model — same honest constraint Day 9's
`success_probability_model` docstring calls out for outcome data: there's
no labeled "this comment indicates team friction" dataset in this system
to train one on, and a short, auditable keyword list is easier for a
mentor to trust or dispute than an opaque score.

## Why neither feature touches `/recommend-teams`

Both are reachable standalone rather than folded into the Day 10
integration endpoint, on purpose:

- **Rebalancing** is trigger-based (a member becoming unavailable), not
  part of initial team formation — it doesn't make sense as a step
  inside `/recommend-teams`, which only ever runs against fresh
  candidate pools.
- **Chemistry** *could* have been attached to every `RecommendedTeamOut`
  the way Day 11's `explanation` was, but was kept standalone instead so
  a mentor can pull it up for any existing team (including ones formed
  before Day 16 shipped) without re-running the whole recommendation
  pipeline — closer to how `GET /compatibility/team/{id}` works than how
  `explanation` does.

## Tests

- `tests/test_team_rebalancing_service.py` — pure-function coverage:
  flags only teams with an unavailable member, picks the closest
  embedding match, returns `None` when no usable candidate exists (either
  side missing an embedding), and never suggests the same replacement to
  two different departures in the same run.
- `tests/test_team_chemistry_service.py` — one strong leader outscores
  two competing ones (and flags it), zero strong leaders flags
  "no clear leader", shared vs. disjoint `project_interests` move the
  score in the right direction, communication spread penalizes uneven
  pairs, feedback sentiment responds to the keyword lists in both
  directions, weights sum to 1.0.
- `tests/test_router_rebalance.py` — the full HTTP flow: 404/409 error
  cases, `GET /rebalance/needed` reflects live availability, a
  deterministic embedding setup proves the *closer* candidate gets
  chosen over a farther one (not just *some* candidate), leadership
  reassignment when a Lead departs, and the "no replacement available"
  path leaves the team both intact and still flagged.
- `tests/test_router_team_chemistry.py` — 404 for an unknown team, full
  response shape, and that the score reflects current membership rather
  than a stale snapshot (adding a second strong leader mid-test lowers
  `leadership_balance` on the next call).

Run everything with:

```bash
docker compose exec backend pytest tests/ -v
```

203 test functions across `tests/` as of Day 16 (28 new: 4 in
`test_team_rebalancing_service.py`, 10 in `test_team_chemistry_service.py`,
7 in `test_router_rebalance.py`, 3 in `test_router_team_chemistry.py`, on
top of Day 15's 175). As with Day 15, this count comes from a static
read of the test files, not a live run in the authoring environment (no
network access here to install `fastapi`/`pytest`/etc.) — run the command
above to confirm the full suite passes before treating either bonus
feature as demo-ready.

**Manual demo, for the two features:** bring the stack up, run
`/recommend-teams` to form a few teams, then (a) mark one member on a
team unavailable via the Admin Dashboard or `PUT /interns/{id}`, hit
`GET /rebalance/needed` to see it flagged, then `POST /rebalance/team/{id}`
to watch the swap and rescore happen; and (b) hit
`GET /team-chemistry/team/{id}` on a couple of different teams — one with
a single clear leader and one with two similarly-scored leaders — to see
the `leadership_balance` component and flag differ between them.
