"""Day 13 — /admin-analytics endpoints.

Read-only aggregation endpoints for the Admin Dashboard. Deliberately no
POST/recalculate here (unlike risk-analysis or success-probability) —
these are rollups over data other engines already wrote (Team.compatibility_score,
Team.success_probability, Team.risk_notes) or plain headcounts, so there's
nothing to persist.

Technology distribution — the fourth metric the execution guide calls out
for Day 13 — isn't duplicated here; it's Day 4's existing
GET /skill-matrix/technology-frequency with no team_id (org-wide scope).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services import admin_analytics_service

router = APIRouter(prefix="/admin-analytics", tags=["admin-analytics"])


@router.get("/teams", response_model=schemas.CrossTeamAnalyticsOut)
def cross_team_analytics(db: Session = Depends(get_db)):
    """Org-wide rollup across every team: size distribution, average
    compatibility/success scores (scored teams only), and how many teams
    have a project and a risk assessment."""
    teams = TeamRepository(db).list_all_with_project_and_members()
    return schemas.CrossTeamAnalyticsOut(**admin_analytics_service.cross_team_analytics(teams))


@router.get("/projects", response_model=schemas.ProjectSuccessRatesOut)
def project_success_rates(db: Session = Depends(get_db)):
    """Per-project rollup: how many teams have been matched to each
    project, and their average success probability / compatibility."""
    projects = ProjectRepository(db).list_all_with_teams()
    return schemas.ProjectSuccessRatesOut(**admin_analytics_service.project_success_rates(projects))


@router.get("/resource-utilization", response_model=schemas.ResourceUtilizationOut)
def resource_utilization(db: Session = Depends(get_db)):
    """Org-wide intern headcount view: assigned vs. still-available
    candidate pool, plus attendance/embedding-coverage signals."""
    interns = InternRepository(db).list_all()
    assigned_ids = TeamRepository(db).assigned_intern_ids()
    return schemas.ResourceUtilizationOut(
        **admin_analytics_service.resource_utilization(interns, assigned_ids)
    )
