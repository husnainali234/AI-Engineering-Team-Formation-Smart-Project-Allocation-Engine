"""
Day 4 — Embedding generation pipeline.

Turns an intern's skill/interest profile into a 384-dim sentence-transformers
embedding (all-MiniLM-L6-v2) and stores it on `Intern.skill_embedding`.

Caching: `Intern.embedding_source_hash` is the SHA-256 of the exact text last
embedded. `generate_for_intern` recomputes the text, hashes it, and skips the
(relatively expensive) model call entirely if the hash is unchanged and an
embedding already exists — so re-running the batch job after importing 100
rows only pays the model cost for the interns whose profile actually changed.
"""
import hashlib
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app import models
from app.ml.embedding_model import get_model
from app.services.skill_utils import intern_proficiency_map

logger = logging.getLogger(__name__)


def build_intern_text(intern: models.Intern) -> str:
    """Compose the text representation of an intern that gets embedded.
    Deliberately semantic/descriptive (not just a CSV dump) since
    sentence-transformers models are trained on natural sentences."""
    parts: list[str] = []

    if intern.technology_stack:
        parts.append(f"Technology stack: {intern.technology_stack}.")

    proficiencies = intern_proficiency_map(intern)
    if proficiencies:
        ranked = sorted(proficiencies.items(), key=lambda kv: kv[1], reverse=True)
        skills_text = ", ".join(f"{name} (proficiency {level}/5)" for name, level in ranked)
        parts.append(f"Skills: {skills_text}.")

    if intern.project_interests:
        parts.append(f"Project interests: {intern.project_interests}.")

    if not parts:
        # Always produce *something* embeddable rather than erroring out on
        # a freshly-created intern with no profile data yet.
        parts.append(f"Intern profile: {intern.full_name}.")

    return " ".join(parts)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def generate_for_intern(intern: models.Intern, force: bool = False) -> bool:
    """Compute (or reuse the cached) embedding for one intern, mutating it
    in place. Does NOT commit — caller controls the transaction so batch
    callers can commit once instead of once per intern.

    Returns True if a new embedding was computed, False if the cached one
    was reused as-is.
    """
    text = build_intern_text(intern)
    new_hash = _hash_text(text)

    if not force and intern.skill_embedding is not None and intern.embedding_source_hash == new_hash:
        return False

    model = get_model()
    vector = model.encode(text)
    intern.skill_embedding = [float(x) for x in vector]
    intern.embedding_source_hash = new_hash
    intern.embedding_updated_at = datetime.utcnow()
    return True


def generate_for_intern_and_commit(db: Session, intern: models.Intern, force: bool = False) -> bool:
    """Single-intern convenience wrapper that also commits — used by the
    /embeddings/interns/{id}/generate endpoint and by the automatic-generation
    hooks in the interns CRUD router."""
    generated = generate_for_intern(intern, force=force)
    if generated:
        db.add(intern)
        db.commit()
        db.refresh(intern)
    return generated


def generate_for_all(db: Session, interns: list[models.Intern], force: bool = False) -> dict:
    """Batch version used by POST /embeddings/generate-all and by the
    /import endpoint's post-import hook. Commits once at the end.

    Individual failures (e.g. a transient model error) are caught so one bad
    row can't abort embedding generation for the rest of the batch — mirrors
    the row-level error tolerance the Day 3 /import endpoint already uses.
    """
    generated = 0
    cached = 0
    errors: list[str] = []

    for intern in interns:
        try:
            if generate_for_intern(intern, force=force):
                generated += 1
            else:
                cached += 1
        except Exception as exc:  # noqa: BLE001 - intentionally broad, see docstring
            errors.append(f"intern_id {intern.id}: {exc}")
            logger.exception("Embedding generation failed for intern_id=%s", intern.id)

    if generated:
        db.commit()

    return {
        "total": len(interns),
        "generated": generated,
        "skipped_cached": cached,
        "errors": errors,
    }
