"""
Day 4 — /embeddings endpoints.

Manual controls around the embedding pipeline that also runs automatically
(see the hooks in routers/interns.py and routers/import_data.py): generate
one intern's embedding on demand, batch-generate/refresh everyone, inspect
an intern's current embedding, and check overall embedding coverage.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.repositories.intern_repository import InternRepository
from app.services import embedding_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/interns/{intern_id}/generate", response_model=schemas.EmbeddingOut)
def generate_intern_embedding(
    intern_id: int,
    force: bool = Query(default=False, description="Recompute even if the cached embedding is still fresh"),
    db: Session = Depends(get_db),
):
    """Generate (or refresh, with `force=true`) one intern's skill
    embedding on demand — the manual counterpart to the automatic
    generation hooks on intern create/update and /import."""
    intern = InternRepository(db).get_by_id_with_skills(intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")

    embedding_service.generate_for_intern_and_commit(db, intern, force=force)

    return schemas.EmbeddingOut(
        intern_id=intern.id,
        dimensions=len(intern.skill_embedding or []),
        embedding=intern.skill_embedding or [],
        embedding_updated_at=intern.embedding_updated_at,
    )


@router.post("/generate-all", response_model=schemas.EmbeddingBatchSummary)
def generate_all_embeddings(
    force: bool = Query(default=False, description="Recompute every intern's embedding, ignoring the cache"),
    db: Session = Depends(get_db),
):
    """Batch embedding generation for every intern — the Day 4
    'automatic embedding generation for every intern' entry point, and what
    the Day 5 checkpoint's Import -> Embedding integration relies on."""
    interns = InternRepository(db).list_all_with_skills()
    summary = embedding_service.generate_for_all(db, interns, force=force)
    return schemas.EmbeddingBatchSummary(**summary)


@router.get("/interns/{intern_id}", response_model=schemas.EmbeddingOut)
def get_intern_embedding(intern_id: int, db: Session = Depends(get_db)):
    """Fetch one intern's current embedding vector (384-dim) plus when it
    was last generated. 409 if the intern exists but has no embedding yet."""
    intern = InternRepository(db).get_by_id(intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")
    if intern.skill_embedding is None:
        raise HTTPException(
            status_code=409,
            detail="No embedding generated yet for this intern — "
                   f"POST /embeddings/interns/{intern_id}/generate first.",
        )

    return schemas.EmbeddingOut(
        intern_id=intern.id,
        dimensions=len(intern.skill_embedding),
        embedding=intern.skill_embedding,
        embedding_updated_at=intern.embedding_updated_at,
    )


@router.get("/status", response_model=list[schemas.EmbeddingStatusOut])
def embedding_status(db: Session = Depends(get_db)):
    """Coverage check — which interns still need an embedding generated.
    Used to verify Day 5's checkpoint ('embeddings generate automatically')."""
    interns = InternRepository(db).list_all()
    return [
        schemas.EmbeddingStatusOut(
            intern_id=i.id,
            full_name=i.full_name,
            has_embedding=i.skill_embedding is not None,
            embedding_updated_at=i.embedding_updated_at,
        )
        for i in interns
    ]
