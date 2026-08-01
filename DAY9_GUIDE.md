# Day 9 — Success Probability + Risk: Full Walkthrough

Goal for today: **every recommended team carries a success probability %
and a list of identified risks.** This is called out in the execution
guide's own list of the hardest ML days ("most likely Day 7, 9, or 11"),
mainly because of one constraint: there's no real "did this team actually
succeed" outcome data anywhere in the system yet. Today's walkthrough
spends most of its time on how that gets handled honestly instead of
quietly ignored.

---

## What's new since Day 8

```
ezitech-ai020/
├── app/
│   ├── ml/
│   │   └── success_probability_model.py   # NEW — lazily-trained LogisticRegression on synthesized outcomes
│   ├── services/
│   │   ├── success_probability_service.py # NEW — team_balance + attendance + feedback -> probability
│   │   └── risk_analysis_service.py       # NEW — rule-based risk flags
│   ├── repositories/
│   │   └── intern_repository.py           # UPDATED — feedback_for_interns()
│   └── routers/
│       ├── success_probability.py         # NEW — /success-probability/*
│       └── risk_analysis.py               # NEW — /risk-analysis/*
└── tests/
    ├── test_success_probability_service.py    # NEW
    ├── test_risk_analysis_service.py          # NEW
    ├── test_router_success_probability.py     # NEW
    └── test_router_risk_analysis.py           # NEW
```

No new tables or columns — `Team.success_probability` and `Team.risk_notes`
have been sitting reserved in the ERD since Day 1, same as `Team.project_id`
was for Day 8.

## 1. Success Probability — training on data that doesn't exist yet

The spec asks for a baseline scikit-learn model trained on historical
outcomes. There are no historical outcomes — no intern cohort has actually
run through this system and produced a real "this team succeeded / failed"
label. Two honest options: skip the ML model and call it a formula instead,
or train on *synthesized* outcomes and be explicit that's what happened.
This goes with the second, because the spec is explicit about wanting a
trained model, and "trained on synthetic data with a documented, simple
prior" is a defensible baseline that's easy to replace once real outcome
data exists (swap the training function in
`app/ml/success_probability_model.py`, nothing downstream changes).

The three inputs are exactly what the spec names — team balance, attendance,
feedback:

| Feature | Source |
|---|---|
| `team_balance` | Day 6/7's skill diversity score (0.0-1.0) |
| `avg_attendance_pct` | mean of `Intern.attendance_pct` across the team |
| `avg_feedback_score` | mean of `MentorFeedback.score` per member, averaged across the team (neutral 5.0 for a member with no feedback on record) |

`app/ml/success_probability_model.py` generates 2000 synthetic rows
(fixed seed) where the "ground truth" label is a coin-flip weighted by
`0.35*balance + 0.30*attendance + 0.35*feedback` plus noise, then fits a
`LogisticRegression` on that. `predict_proba` gives a genuine probability,
not a threshold — the model is lazily trained once per process and cached,
same pattern as `app/ml/embedding_model.py`.

```bash
curl http://localhost:8000/success-probability/team/5
```

```json
{
  "team_id": 5,
  "team_name": "Auto-Formed Team 1",
  "success_probability": 77.79,
  "features": {
    "team_balance": 1.0,
    "avg_attendance_pct": 87.5,
    "avg_feedback_score": 5.0
  }
}
```

Read-only preview by default — like every other engine so far. To persist:

```bash
curl -X POST http://localhost:8000/success-probability/team/5/recalculate
```

Writes to `Team.success_probability` — stored as 0.0-1.0 per the Day 1 ERD
comment (`# 0-1, from Performance Analytics Engine`), even though the API
response is a 0-100 percentage for readability.

## 2. Risk Analysis — rules, not a second model

Unlike Success Probability, Risk Analysis is deliberately **not** ML —
`app/services/risk_analysis_service.py` is four threshold checks:

| Risk | Trigger |
|---|---|
| `skill_overlap` | team skill diversity < 0.55 (0.5 = identical skill sets) |
| `low_attendance` | any member's `attendance_pct` < 75% |
| `leadership_gap` | no member's `leadership_score` >= 6.0 |
| `high_conflict_likelihood` | `Team.compatibility_score` < 50 (skipped entirely if compatibility hasn't been calculated yet — see design notes) |

```bash
curl http://localhost:8000/risk-analysis/team/5
```

```json
{
  "team_id": 5,
  "team_name": "Auto-Formed Team 1",
  "risks": [
    {
      "type": "low_attendance",
      "severity": "high",
      "message": "Below-threshold attendance (75%): Priya N."
    }
  ]
}
```

Empty `risks: []` for a team with no flags — not a placeholder message, an
actual empty list, so a dashboard can render "No risks identified" or a
green checkmark without special-casing.

```bash
curl -X POST http://localhost:8000/risk-analysis/team/5/recalculate
```

Persists a human-readable summary onto `Team.risk_notes` (a `Text` column,
not structured JSON — `risk_notes` reads like something a mentor wrote, so
the persisted format matches that: `"[HIGH] low_attendance: Below-threshold
attendance (75%): Priya N."`).

## 3. Run the test suite

```bash
docker compose exec backend pytest tests/ -v
```

`test_success_probability_service.py` covers the feature computation
directly: bounded output, the empty-team edge case, the neutral-feedback
default, feedback averaging, and a monotonicity sanity check (a team with
stronger signals across the board scores a higher probability than one
with weaker signals — this doesn't prove the model is "correct", since
there's no ground truth to be correct against yet, but it does prove the
synthetic prior it was trained on is actually reflected in its
predictions). `test_risk_analysis_service.py` covers each of the four
rules independently, plus the "no risks" and "compatibility not yet
calculated" cases. The two router files integration-test the HTTP layer,
including the 404/409 paths and that `/recalculate` actually persists.

## 4. Commit

```bash
git add .
git commit -m "Day 9: Success Probability model (scikit-learn, synthesized training data) and rule-based Risk Analysis"
git push
```

## Design notes worth knowing

- **Why synthesized training data instead of a hand-written formula**: the
  spec is explicit about wanting a trained scikit-learn model here (Risk
  Analysis, right next to it, is explicitly rule-based instead — the spec
  wants both approaches represented). Training on synthetic data with a
  simple, documented prior is honest about what "trained" means today
  without pretending there's real historical signal behind it, and it's a
  clean seam to swap in real data later — only `_generate_synthetic_training_data()`
  changes, `predict_success_probability()`'s interface doesn't.
- **Why the risk-check severity thresholds are separate named constants,
  not inline magic numbers**: same reasoning as Day 7/9's other weight/
  threshold constants (`LEADERSHIP_WEIGHTS`, `COMPATIBILITY_WEIGHTS`) — a
  mentor tuning "what counts as low attendance" should be able to change
  one number, not hunt through conditional logic.
- **Why `high_conflict_likelihood` is skipped entirely (not scored as
  "high risk") when `compatibility_score` is `None`/`0.0`**: same "absence
  of data isn't evidence" principle used for team-history defaults in
  leadership_service and compatibility_service — a team that simply hasn't
  had `/compatibility/team/{id}/recalculate` run yet shouldn't look
  riskier than one that has and scored well.
- **Why Success Probability and Risk Analysis are separate services and
  separate routers**, rather than one combined "team health" endpoint:
  the same "each engine independently useful and independently testable"
  principle every day since Day 6 has followed. A mentor might want to
  recalculate risk flags after nudging a team's compatibility score without
  retraining/reevaluating success probability, or vice versa — and Day 10's
  `/recommend-teams` is exactly where they get composed together, not here.

## End-of-Day 9 Checklist

- [ ] `GET /success-probability/team/{id}` returns a 0-100 probability plus
      the three underlying feature values, `409` for a team with no members
- [ ] `POST /success-probability/team/{id}/recalculate` persists to
      `Team.success_probability` as 0.0-1.0
- [ ] `GET /risk-analysis/team/{id}` returns `risks: []` for a healthy team,
      up to four named risk types otherwise
- [ ] `POST /risk-analysis/team/{id}/recalculate` persists a readable
      summary to `Team.risk_notes`
- [ ] `pytest tests/` (full Day 1-9 suite) passes
- [ ] Everything committed and pushed

If all boxes are checked, every team now carries a success probability and
an explainable risk list — today's deliverable — and Day 10's Checkpoint 2
has all six engines (matching, compatibility, team formation, leadership,
project matching, workload, success probability, risk) sitting behind
independent, tested endpoints, ready to be wired into one
`/recommend-teams` call.
