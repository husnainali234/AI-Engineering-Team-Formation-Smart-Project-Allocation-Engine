from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routers import (
    interns, projects, teams, import_data,
    embeddings, skill_matrix, matching, compatibility, recommendations,
    leadership, team_formation, project_matching, workload,
    success_probability, risk_analysis,
    recommend_teams,
    admin_analytics,
    student_dashboard,
    team_rebalancing,
    team_chemistry,
    knowledge_graph,
)

# Day 12 — API Finalization: descriptions for every route group, so Swagger
# (/docs) reads as documentation rather than just a list of endpoints. Order
# here also controls the order route groups render in Swagger, so it's kept
# in the same day-by-day sequence the rest of the docs use.
TAGS_METADATA = [
    {"name": "meta", "description": "Service liveness/readiness checks."},
    {"name": "interns", "description": "Day 1-3 — CRUD for intern profiles."},
    {"name": "projects", "description": "Day 1-3 — CRUD for candidate projects."},
    {"name": "teams", "description": "Day 1-3 — CRUD for teams and their membership."},
    {"name": "import", "description": "Day 3 — bulk CSV/JSON upsert of intern records (simulates the Ezitech portal export)."},
    {"name": "embeddings", "description": "Day 4 — Sentence-Transformers embedding pipeline for intern skill/interest text."},
    {"name": "skill-matrix", "description": "Day 4 — per-skill frequency and proficiency aggregation, org-wide or per-team."},
    {"name": "matching", "description": "Day 6 — Skill Matching Engine: cosine-similarity teammate recommendations and team diversity."},
    {"name": "compatibility", "description": "Day 6 — Collaboration Prediction Model: pairwise and team-level Compatibility Score."},
    {"name": "recommendations", "description": "Day 6 — blended teammate recommendations (similarity + compatibility)."},
    {"name": "leadership", "description": "Day 7 — Leadership Detection: per-intern scoring and team leader suggestion."},
    {"name": "team-formation", "description": "Day 7 — Team Formation Engine: KMeans/Agglomerative clustering into balanced teams."},
    {"name": "project-matching", "description": "Day 8 — Project Recommendation Engine: match a team's skills against project requirements."},
    {"name": "workload", "description": "Day 8 — Workload Distribution: per-member responsibility assignment for a team's project."},
    {"name": "success-probability", "description": "Day 9 — trained success-probability model, with a Day 11 SHAP-based explanation attached."},
    {"name": "risk-analysis", "description": "Day 9 — rule-based risk flags (skill overlap, low attendance, leadership gap, conflict likelihood)."},
    {"name": "recommend-teams", "description": "Day 10 — Checkpoint 2: the single integration endpoint wiring every engine together."},
    {"name": "admin-analytics", "description": "Day 13 — org-wide rollups for the Admin Dashboard: cross-team analytics, project success rates, resource utilization."},
    {"name": "student-dashboard", "description": "Day 14 — a single intern's own view: assigned team, role, compatibility score, strengths, responsibilities."},
    {"name": "rebalance", "description": "Day 16 (bonus) — Automatic Team Rebalancing: detect and replace unavailable team members, rescoring the team afterward."},
    {"name": "team-chemistry", "description": "Day 16 (bonus) — Team Chemistry Prediction: a team-level interpersonal-friction signal distinct from Compatibility and Success Probability."},
    {"name": "knowledge-graph", "description": "Gap-fix (post-Day-20) — Engineering Knowledge Graph: NetworkX in-process graph over interns/skills/teams/projects, with skill-neighbor lookup, graph-native collaborator recommendations, and explainable connection paths."},
]

app = FastAPI(
    title="Ezitech AI-020: Team Formation & Project Allocation Engine",
    description=(
        "AI-powered engine that forms balanced engineering teams and recommends projects. "
        "Seven engines — Skill Matching, Team Formation, Collaboration Prediction, Project "
        "Recommendation, Performance Analytics (Success Probability + Risk), an "
        "Explainable AI Layer (SHAP), and an Engineering Knowledge Graph (NetworkX) — sit "
        "behind this API, all wired together by POST /recommend-teams."
    ),
    version="0.19.0",
    openapi_tags=TAGS_METADATA,
)

# Day 18: origins come from ALLOWED_ORIGINS (app/config.py) — defaults to
# "*" so nothing changes for local dev; set to the actual dashboard origin
# in a hosted deployment's environment instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interns.router)
app.include_router(projects.router)
app.include_router(teams.router)
app.include_router(import_data.router)

# Day 4-6: embeddings, skill matrix, matching, compatibility, recommendations
app.include_router(embeddings.router)
app.include_router(skill_matrix.router)
app.include_router(matching.router)
app.include_router(compatibility.router)
app.include_router(recommendations.router)

# Day 7: leadership detection, team formation
app.include_router(leadership.router)
app.include_router(team_formation.router)

# Day 8: project recommendation, workload distribution
app.include_router(project_matching.router)
app.include_router(workload.router)

# Day 9: success probability, risk analysis
app.include_router(success_probability.router)
app.include_router(risk_analysis.router)

# Day 10: Checkpoint 2 — all engines wired together
app.include_router(recommend_teams.router)

# Day 13: Admin Dashboard analytics endpoints
app.include_router(admin_analytics.router)

# Day 14: Student Dashboard
app.include_router(student_dashboard.router)

# Day 16: bonus features — Automatic Team Rebalancing, Team Chemistry Prediction
app.include_router(team_rebalancing.router)
app.include_router(team_chemistry.router)

# Gap-fix (post-Day-20): Engineering Knowledge Graph (case study's AI
# Architecture Requirements list — was never wired up in Days 1-20)
app.include_router(knowledge_graph.router)


@app.get("/", tags=["meta"])
def root():
    return {"service": "AI-020 Team Formation Engine", "status": "running"}


@app.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    """Confirms the API is up AND can reach Postgres."""
    db.execute(text("SELECT 1"))
    return {"api": "ok", "database": "ok"}
