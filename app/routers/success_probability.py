"""Day 9 — /success-probability endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import success_probability_service

router = APIRouter(prefix="/success-probability", tags=["success-probability"])


def _load_team_and_members(team_id: int, db: Session):
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    members = InternRepository(db).list_by_team(team_id)
    if not members:
        raise HTTPException(status_code=409, detail="Team has no members")
    return team, members


def _feedback_by_intern(intern_repo: InternRepository, member_ids: list[int]) -> dict[int, list[models.MentorFeedback]]:
    feedback_by_intern: dict[int, list[models.MentorFeedback]] = {}
    for entry in intern_repo.feedback_for_interns(member_ids):
        feedback_by_intern.setdefault(entry.intern_id, []).append(entry)
    return feedback_by_intern


@router.get("/team/{team_id}", response_model=schemas.SuccessProbabilityOut)
def preview_success_probability(team_id: int, db: Session = Depends(get_db)):
    """Read-only, like Day 6/8's GET .../recalculate-adjacent endpoints —
    nothing is written until you explicitly recalculate."""
    team, members = _load_team_and_members(team_id, db)
    feedback_by_intern = _feedback_by_intern(InternRepository(db), [m.id for m in members])
    result = success_probability_service.compute_success_probability(members, feedback_by_intern)

    return schemas.SuccessProbabilityOut(
        team_id=team.id,
        team_name=team.name,
        success_probability=result["success_probability"],
        features=result["features"],
        explanation=schemas.ExplanationOut(**result["explanation"]),
    )


@router.post("/team/{team_id}/recalculate", response_model=schemas.SuccessProbabilityOut)
def recalculate_success_probability(team_id: int, db: Session = Depends(get_db)):
    """Persists to Team.success_probability (0-1, per the Day 1 ERD) — the
    field reserved for exactly this since the original schema draft."""
    team_repo = TeamRepository(db)
    team, members = _load_team_and_members(team_id, db)
    feedback_by_intern = _feedback_by_intern(InternRepository(db), [m.id for m in members])
    result = success_probability_service.compute_success_probability(members, feedback_by_intern)

    team.success_probability = result["success_probability"] / 100.0
    team_repo.save(team)

    return schemas.SuccessProbabilityOut(
        team_id=team.id,
        team_name=team.name,
        success_probability=result["success_probability"],
        features=result["features"],
        explanation=schemas.ExplanationOut(**result["explanation"]),
    )
