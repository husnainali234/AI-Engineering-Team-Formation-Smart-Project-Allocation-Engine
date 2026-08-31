"""
Day 3 — CRUD endpoints for Team.

Teams are the one entity with a real sub-resource (members), because the
Team Formation Engine (Day 7) will populate `members` programmatically, not
just via manual POST. Two extra endpoints handle that:

    POST   /teams/{id}/members       -> add one intern to a team
    DELETE /teams/{id}/members/{iid} -> remove one intern from a team
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[schemas.TeamOut])
def list_teams(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Team)
    if project_id is not None:
        query = query.filter(models.Team.project_id == project_id)
    return query.order_by(models.Team.id).offset(skip).limit(limit).all()


@router.get("/{team_id}", response_model=schemas.TeamOut)
def get_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("", response_model=schemas.TeamOut, status_code=201)
def create_team(payload: schemas.TeamCreate, db: Session = Depends(get_db)):
    if payload.project_id is not None and not db.get(models.Project, payload.project_id):
        raise HTTPException(status_code=404, detail="project_id does not exist")

    data = payload.model_dump(exclude={"member_ids"})
    team = models.Team(**data)
    db.add(team)
    db.flush()  # get team.id without committing yet

    for intern_id in payload.member_ids:
        if not db.get(models.Intern, intern_id):
            raise HTTPException(status_code=404, detail=f"intern_id {intern_id} does not exist")
        db.add(models.TeamMember(team_id=team.id, intern_id=intern_id))

    db.commit()
    db.refresh(team)
    return team


@router.put("/{team_id}", response_model=schemas.TeamOut)
def update_team(team_id: int, payload: schemas.TeamUpdate, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    updates = payload.model_dump(exclude_unset=True)
    if "project_id" in updates and updates["project_id"] is not None:
        if not db.get(models.Project, updates["project_id"]):
            raise HTTPException(status_code=404, detail="project_id does not exist")

    for field, value in updates.items():
        setattr(team, field, value)

    db.commit()
    db.refresh(team)
    return team


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: int, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    db.delete(team)   # cascade="all, delete-orphan" on Team.members handles the junction rows
    db.commit()
    return None


@router.post("/{team_id}/members", response_model=schemas.TeamMemberOut, status_code=201)
def add_member(team_id: int, payload: schemas.TeamMemberCreate, db: Session = Depends(get_db)):
    team = db.get(models.Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if not db.get(models.Intern, payload.intern_id):
        raise HTTPException(status_code=404, detail="Intern not found")

    already = (
        db.query(models.TeamMember)
        .filter_by(team_id=team_id, intern_id=payload.intern_id)
        .first()
    )
    if already:
        raise HTTPException(status_code=409, detail="Intern is already on this team")

    member = models.TeamMember(team_id=team_id, **payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{team_id}/members/{intern_id}", status_code=204)
def remove_member(team_id: int, intern_id: int, db: Session = Depends(get_db)):
    member = (
        db.query(models.TeamMember)
        .filter_by(team_id=team_id, intern_id=intern_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=404, detail="This intern is not on this team")
    db.delete(member)
    db.commit()
    return None
