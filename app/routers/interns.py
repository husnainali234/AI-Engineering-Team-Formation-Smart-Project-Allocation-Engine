"""
Day 3 — CRUD endpoints for Intern.

Standard REST shape, reused for projects.py and teams.py:
    GET    /interns          -> list (paginated)
    GET    /interns/{id}     -> one
    POST   /interns          -> create
    PUT    /interns/{id}     -> full/partial update
    DELETE /interns/{id}     -> delete
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import embedding_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interns", tags=["interns"])


def _regenerate_embedding_best_effort(db: Session, intern: models.Intern) -> None:
    """Day 4: automatic embedding generation whenever an intern's profile is
    created or updated. Deliberately best-effort — if the embedding model
    isn't available (e.g. not yet downloaded, no network), the CRUD
    operation that triggered this must still succeed; the intern just stays
    without an embedding until POST /embeddings/generate-all is run."""
    try:
        embedding_service.generate_for_intern_and_commit(db, intern)
    except Exception:  # noqa: BLE001 - see docstring: never let this break CRUD
        logger.exception("Automatic embedding generation failed for intern_id=%s", intern.id)


@router.get("", response_model=list[schemas.InternOut])
def list_interns(
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    technology_stack: str | None = None,
    is_available: bool | None = None,
    db: Session = Depends(get_db),
):
    """List interns with basic pagination and optional filters — the filters
    matter later for Team Formation (Day 7), which needs to pull only
    available interns on a given tech stack."""
    query = db.query(models.Intern)
    if technology_stack:
        query = query.filter(models.Intern.technology_stack.ilike(f"%{technology_stack}%"))
    if is_available is not None:
        query = query.filter(models.Intern.is_available == is_available)
    return query.order_by(models.Intern.id).offset(skip).limit(limit).all()


@router.get("/{intern_id}", response_model=schemas.InternOut)
def get_intern(intern_id: int, db: Session = Depends(get_db)):
    intern = db.get(models.Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")
    return intern


@router.post("", response_model=schemas.InternOut, status_code=201)
def create_intern(payload: schemas.InternCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Intern).filter(models.Intern.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An intern with this email already exists")

    intern = models.Intern(**payload.model_dump())
    db.add(intern)
    db.commit()
    db.refresh(intern)

    _regenerate_embedding_best_effort(db, intern)
    return intern


@router.put("/{intern_id}", response_model=schemas.InternOut)
def update_intern(intern_id: int, payload: schemas.InternUpdate, db: Session = Depends(get_db)):
    intern = db.get(models.Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")

    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] != intern.email:
        clash = db.query(models.Intern).filter(models.Intern.email == updates["email"]).first()
        if clash:
            raise HTTPException(status_code=409, detail="Another intern already uses this email")

    for field, value in updates.items():
        setattr(intern, field, value)

    db.commit()
    db.refresh(intern)

    _regenerate_embedding_best_effort(db, intern)
    return intern


@router.delete("/{intern_id}", status_code=204)
def delete_intern(intern_id: int, db: Session = Depends(get_db)):
    intern = db.get(models.Intern, intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")
    db.delete(intern)
    db.commit()
    return None
