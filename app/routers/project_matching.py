"""Day 8 — /project-matching endpoints (Project Recommendation Engine)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services import project_recommendation_service

router = APIRouter(prefix="/project-matching", tags=["project-matching"])


@router.get("/team/{team_id}", response_model=schemas.ProjectRecommendationsOut)
def recommend_projects_for_team(team_id: int, db: Session = Depends(get_db)):
    """Read-only, like Day 6/7's GET .../suggest endpoints — nothing is
    written until you explicitly assign."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    if not members:
        raise HTTPException(status_code=409, detail="Team has no members")

    projects = ProjectRepository(db).list_all()
    if not projects:
        raise HTTPException(status_code=409, detail="No projects exist to recommend")

    team_skills = project_recommendation_service.team_skill_set(members)
    ranked = project_recommendation_service.recommend_projects(members, projects)

    return schemas.ProjectRecommendationsOut(
        team_id=team.id,
        team_name=team.name,
        team_skill_count=len(team_skills),
        recommendations=[schemas.ProjectFitOut(**r) for r in ranked],
    )


@router.post("/team/{team_id}/assign", response_model=schemas.ProjectFitOut)
def assign_project(
    team_id: int,
    project_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Persists to Team.project_id — the field Day 1's ERD already
    reserved for this. Pin a specific project_id, or omit it to
    auto-pick the top recommendation."""
    team_repo = TeamRepository(db)
    team = team_repo.get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    if not members:
        raise HTTPException(status_code=409, detail="Team has no members")

    project_repo = ProjectRepository(db)

    if project_id is not None:
        project = project_repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        team_skills = project_recommendation_service.team_skill_set(members)
        fit = project_recommendation_service.score_project_fit(team_skills, project)
    else:
        projects = project_repo.list_all()
        if not projects:
            raise HTTPException(status_code=409, detail="No projects exist to recommend")
        fit = project_recommendation_service.recommend_projects(members, projects)[0]

    team.project_id = fit["project_id"]
    team_repo.save(team)

    return schemas.ProjectFitOut(**fit)
