"""Day 16 — Bonus Feature (Engineer B): /team-chemistry endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import team_chemistry_service

router = APIRouter(prefix="/team-chemistry", tags=["team-chemistry"])


@router.get("/team/{team_id}", response_model=schemas.TeamChemistryOut)
def team_chemistry(team_id: int, db: Session = Depends(get_db)):
    """Team Chemistry Prediction — a team-level interpersonal-friction
    signal distinct from Day 6's pairwise Compatibility Score and Day 9's
    project-outcome Success Probability (see team_chemistry_service's
    module docstring for why those two don't already cover this).
    Recomputed live on every call, same as GET /compatibility/team/{id} —
    deliberately never persisted, so it can't go stale relative to the
    team's current membership or the mentor feedback on record."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    feedback_entries = InternRepository(db).feedback_for_interns([m.id for m in members])

    result = team_chemistry_service.predict_team_chemistry(members, feedback_entries)

    return schemas.TeamChemistryOut(
        team_id=team.id,
        team_name=team.name,
        member_count=result["member_count"],
        chemistry_score=result["chemistry_score"],
        label=result["label"],
        components={k: schemas.ChemistryComponentOut(**v) for k, v in result["components"].items()},
        flags=result["flags"],
    )
