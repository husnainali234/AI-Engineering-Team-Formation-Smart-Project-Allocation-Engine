"""Day 8 — /workload endpoints (Workload Distribution)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services import workload_service

router = APIRouter(prefix="/workload", tags=["workload"])


def _load_team_and_project(team_id: int, db: Session):
    team = TeamRepository(db).get_by_id_with_members_and_interns(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not team.members:
        raise HTTPException(status_code=409, detail="Team has no members")
    if not team.project_id:
        raise HTTPException(status_code=409, detail="Team has no project assigned yet")

    project = ProjectRepository(db).get_by_id(team.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Assigned project not found")

    return team, project


@router.get("/team/{team_id}", response_model=schemas.WorkloadOut)
def preview_workload(team_id: int, db: Session = Depends(get_db)):
    """Read-only preview; 409 if the team has no project assigned yet —
    workload only makes sense once you know what the team is building."""
    team, project = _load_team_and_project(team_id, db)
    rows = workload_service.distribute_workload(team.members, project)

    return schemas.WorkloadOut(
        team_id=team.id,
        team_name=team.name,
        project_id=project.id,
        project_title=project.title,
        assignments=[schemas.WorkloadAssignmentOut(**r) for r in rows],
    )


@router.post("/team/{team_id}/apply", response_model=schemas.WorkloadOut)
def apply_workload(team_id: int, db: Session = Depends(get_db)):
    """Persists each entry's suggested_responsibility onto its TeamMember
    row — the field the original Day 1 ERD reserved for exactly this."""
    team, project = _load_team_and_project(team_id, db)
    rows = workload_service.distribute_workload(team.members, project)

    rows_by_intern = {r["intern_id"]: r for r in rows}
    for tm in team.members:
        row = rows_by_intern.get(tm.intern_id)
        if row:
            tm.suggested_responsibility = row["suggested_responsibility"]
            db.add(tm)
    db.commit()

    return schemas.WorkloadOut(
        team_id=team.id,
        team_name=team.name,
        project_id=project.id,
        project_title=project.title,
        assignments=[schemas.WorkloadAssignmentOut(**r) for r in rows],
    )
