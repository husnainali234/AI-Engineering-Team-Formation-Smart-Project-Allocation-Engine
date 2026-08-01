# Day 11 — Explainability + Dashboard Scaffold

## Goal

Per the execution guide's Week 3 kickoff: add an Explainable AI Layer
(SHAP on the success-probability model, plus human-readable reason
generation) so every prediction the system makes comes with a "why," and
scaffold the three-role dashboard app (Streamlit) so Days 12-14 have
somewhere to build real pages into.

## Part 1 — Explainable AI Layer

### Why SHAP, and why only on the success-probability model

The execution guide's tech-stack table calls out SHAP specifically for
explaining `RandomForest`/`LogisticRegression` outputs — and the only
trained ML model in this codebase (as opposed to the rule-based engines:
Risk Analysis, Workload Distribution, Team Formation's round-robin) is
Day 9's success-probability `LogisticRegression`. Everything else in this
project is already explainable by construction — Compatibility, Risk
Analysis, and Workload Distribution all return their own weighted
breakdowns or explicit rule matches — so SHAP's job here is specifically
to explain the one model whose coefficients aren't already surfaced
anywhere.

### How it works

`app/services/explainability_service.py`:

1. Builds a `shap.LinearExplainer` around the trained model
   (`app/ml/success_probability_model.get_model()`) and a fixed-seed
   background sample drawn from the same synthetic training distribution
   the model itself was fit on (`get_background_sample()`).
2. For a given team's three inputs (`team_balance`, `avg_attendance_pct`,
   `avg_feedback_score`), computes each feature's SHAP value — its signed
   contribution, in the model's log-odds space, relative to that
   background.
3. Converts the SHAP values into:
   - `factors`: a structured list (`feature`, `value`, `shap_value`,
     `direction`) for anything that wants to render this as a mini bar
     chart.
   - `reasons`: one plain-English sentence per feature (e.g. *"Average
     mentor feedback (7.5/10) increased the predicted success
     probability."*).
   - `summary`: a single sentence naming the strongest driver overall.

### Why `LinearExplainer`, not `KernelExplainer`/`TreeExplainer`

The model is a plain 3-feature logistic regression — a genuinely linear
model — so `LinearExplainer` gives an *exact* closed-form attribution
(`coefficient × (value - background mean)`), not a sampling-based
approximation. Same "simplest tool that satisfies the requirement"
reasoning used everywhere else in this project (Day 7's round-robin
assembly, Day 8's greedy workload assignment): a general-purpose explainer
would cost more (slower, non-deterministic without careful seeding) for no
extra correctness, since the model really is linear.

### Where the explanation shows up

- `GET /success-probability/team/{id}` and
  `POST /success-probability/team/{id}/recalculate` — both now return an
  `explanation` field alongside `success_probability` and `features`.
- `POST /recommend-teams` — each `RecommendedTeamOut` now also carries its
  own `explanation`, computed from the same success-probability inputs
  already being calculated for that team. This matches the architecture
  doc's framing of the Explainable AI Layer as "SHAP-based reasons
  attached to *every* recommendation, surfaced identically in all three
  dashboards" — not a one-off endpoint bolted on the side.

`recommend_teams_service.compute_team_recommendation` simply forwards the
`explanation` dict that `success_probability_service.compute_success_probability`
already produces internally — no duplicate SHAP computation per team.

### Schema

```
SuccessFactorOut:  {feature, value, shap_value, direction}
ExplanationOut:    {base_value, factors: [SuccessFactorOut], summary, reasons}
```

`direction` is `"increased"`, `"decreased"`, or `"neutral"` (SHAP magnitude
below a small threshold — see `_NEGLIGIBLE_SHAP_THRESHOLD` — is treated as
no real effect rather than manufacturing a sentence about noise).

### Tests

- `tests/test_explainability_service.py` — all three features present,
  determinism (same input → same output, since both the model and the
  background sample are fixed-seed), correct directions for
  strong-vs-weak signals, and a SHAP additivity sanity check
  (`base_value + Σ shap_value ≈ model.decision_function(X)`).
- Extended `tests/test_router_success_probability.py` and
  `tests/test_router_recommend_teams.py` to assert the `explanation` field
  is present and well-formed on the actual HTTP responses.

## Part 2 — Dashboard scaffold

A new `dashboard/` directory, a separate Streamlit app (its own
`requirements.txt`/`Dockerfile`, wired into `docker-compose.yml` as a
`dashboard` service) — kept separate from the FastAPI backend's
dependencies on purpose, since `streamlit` and `fastapi` pin conflicting
`starlette` versions; running them in the same environment doesn't work,
running them in separate containers (as intended) does.

```
dashboard/
  Home.py                          # entry point + backend health check
  pages/
    1_🧑‍🏫_Mentor_Dashboard.py     # skeleton — full content Day 12
    2_🛠️_Admin_Dashboard.py        # skeleton — full content Day 13
    3_🎓_Student_Dashboard.py      # skeleton — full content Day 14
  lib/
    api_client.py                  # thin requests wrapper shared by all pages
  requirements.txt
  Dockerfile
```

**Why Streamlit's own `pages/` directory, not a hand-rolled router:**
Streamlit auto-generates sidebar navigation from any `.py` files in
`pages/` next to the entry script — that's the "role-based navigation"
requirement satisfied for free, no custom routing/state-machine code
needed. Same "use the simplest tool that satisfies the requirement"
principle the execution guide itself argues for (it's *why* the guide
recommends Streamlit over React in the first place).

**What each page does today:** each role page is a labeled placeholder
("full content arrives Day N") plus one real, working call into the
backend (`GET /teams`, `/interns`, `/projects`, or `/interns/{id}`) — so
the Day 11 deliverable ("dashboard skeleton runs locally with working
navigation") is actually wired to live data, not just static text.

**Run it:**

```bash
docker compose up                 # dashboard at http://localhost:8501
# or locally, without Docker:
cd dashboard
pip install -r requirements.txt
BACKEND_URL=http://localhost:8000 streamlit run Home.py
```

Verified locally (isolated virtualenv, to mirror the separate-container
setup): the app boots headless and serves HTTP 200 on `/`, and all three
role pages import without error.

## Running everything

```bash
docker compose exec backend pytest tests/ -v
```

156 tests pass across Days 1-11 (in-memory SQLite; `shap`'s `LinearExplainer`
needs no network access or downloaded model weights, same as the rest of
the ML stack in tests — only `sentence-transformers` is ever mocked out,
via `fake_embedding_model`, and that's unrelated to Day 11's SHAP work).
