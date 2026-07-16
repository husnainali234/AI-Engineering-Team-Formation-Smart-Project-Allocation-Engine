"""Day 3 — CRUD endpoints for Project. Same shape as interns.py."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    difficulty_level: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Project)
    if difficulty_level:
        query = query.filter(models.Project.difficulty_level == difficulty_level)
    return query.order_by(models.Project.id).offset(skip).limit(limit).all()


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=schemas.ProjectOut, status_code=201)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)):
    project = models.Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.put("/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.teams:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a project that has teams assigned to it — reassign or delete those teams first.",
        )

    db.delete(project)
    db.commit()
    return None
