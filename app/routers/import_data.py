"""
Day 3 — /import endpoint.

Simulates the "integrate directly with the Ezitech Internship Portal" requirement
from the case study: a real portal would push a CSV or JSON export of intern
records; this endpoint accepts either and upserts Intern rows by email.

Accepted formats (detected from filename extension):
    .csv   -> same columns generate_mock_data.py writes to data/interns_seed.csv
    .json  -> a JSON array of objects with the same field names as InternCreate

Behavior:
    - email is the natural key: existing intern with that email is updated,
      otherwise a new one is created.
    - bad rows (missing required field, bad type) are collected into `errors`
      and skipped rather than failing the whole import — a real portal export
      of 100+ rows shouldn't be all-or-nothing.
"""
import csv
import io
import json

import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.services import embedding_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["import"])

REQUIRED_CSV_COLUMNS = {"full_name", "email"}


def _row_to_intern_fields(row: dict) -> dict:
    """Coerce raw string/JSON values into the types InternCreate expects."""
    fields = {}
    for key in (
        "full_name", "email", "technology_stack", "github_url",
        "project_interests",
    ):
        if row.get(key) not in (None, ""):
            fields[key] = row[key]

    for key in ("github_contributions", "engineering_credits"):
        if row.get(key) not in (None, ""):
            fields[key] = int(row[key])

    for key in ("case_study_performance", "attendance_pct", "leadership_score", "communication_score"):
        if row.get(key) not in (None, ""):
            fields[key] = float(row[key])

    if row.get("is_available") not in (None, ""):
        val = row["is_available"]
        if isinstance(val, str):
            fields["is_available"] = val.strip().lower() in ("true", "1", "yes")
        else:
            fields["is_available"] = bool(val)

    return fields


def _upsert_intern(db: Session, fields: dict) -> tuple[str, models.Intern]:
    """Returns ('created' | 'updated', the intern instance)."""
    validated = schemas.InternCreate(**fields)  # raises pydantic.ValidationError on bad data

    existing = db.query(models.Intern).filter(models.Intern.email == validated.email).first()
    if existing:
        for field, value in validated.model_dump().items():
            setattr(existing, field, value)
        return "updated", existing

    intern = models.Intern(**validated.model_dump())
    db.add(intern)
    return "created", intern


@router.post("/import", response_model=schemas.ImportSummary)
def import_interns(
    file: UploadFile = File(..., description="CSV or JSON export of intern records"),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").lower()
    raw = file.file.read()

    if filename.endswith(".csv"):
        source_format = "csv"
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if reader.fieldnames and not REQUIRED_CSV_COLUMNS.issubset(set(reader.fieldnames)):
            raise HTTPException(
                status_code=422,
                detail=f"CSV must include at least these columns: {sorted(REQUIRED_CSV_COLUMNS)}",
            )
    elif filename.endswith(".json"):
        source_format = "json"
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid JSON: {exc}")
        if not isinstance(parsed, list):
            raise HTTPException(status_code=422, detail="JSON file must contain a top-level array of intern objects")
        rows = parsed
    else:
        raise HTTPException(status_code=422, detail="Only .csv or .json files are accepted")

    created = updated = skipped = 0
    errors: list[str] = []
    touched_interns: list[models.Intern] = []

    for i, row in enumerate(rows, start=1):
        try:
            fields = _row_to_intern_fields(row)
            result, intern = _upsert_intern(db, fields)
            created += result == "created"
            updated += result == "updated"
            touched_interns.append(intern)
        except (ValidationError, ValueError, TypeError) as exc:
            skipped += 1
            errors.append(f"Row {i} ({row.get('email', 'no email')}): {exc}")

    db.commit()
    for intern in touched_interns:
        db.refresh(intern)

    # Day 4/5 integration: every imported/updated intern gets an embedding
    # automatically, right after the import lands in the database. Kept
    # best-effort (never raises) so a model/ML issue can't fail an import
    # that otherwise succeeded — matches the row-level tolerance above.
    embedding_summary = None
    try:
        embedding_summary = schemas.EmbeddingBatchSummary(
            **embedding_service.generate_for_all(db, touched_interns)
        )
    except Exception:  # noqa: BLE001 - see docstring
        logger.exception("Post-import embedding generation failed")

    return schemas.ImportSummary(
        source_format=source_format,
        rows_received=len(rows),
        interns_created=created,
        interns_updated=updated,
        rows_skipped=skipped,
        errors=errors[:20],  # cap so one bad file doesn't blow up the response
        embedding_summary=embedding_summary,
    )
