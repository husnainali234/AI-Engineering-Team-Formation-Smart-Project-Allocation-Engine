"""Day 9 — /risk-analysis endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import risk_analysis_service

router = APIRouter(prefix="/risk-analysis", tags=["risk-analysis"])


def _load_team_and_members(team_id: int, db: Session):
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    members = InternRepository(db).list_by_team(team_id)
    if not members:
        raise HTTPException(status_code=409, detail="Team has no members")
    return team, members


def _format_risk_notes(risks: list[dict]) -> str:
    if not risks:
        return "No risks identified."
    return "; ".join(f"[{r['severity'].upper()}] {r['type']}: {r['message']}" for r in risks)


@router.get("/team/{team_id}", response_model=schemas.RiskAnalysisOut)
def preview_risk_analysis(team_id: int, db: Session = Depends(get_db)):
    """Read-only preview; nothing is written until you explicitly
    recalculate."""
    team, members = _load_team_and_members(team_id, db)
    risks = risk_analysis_service.assess_risks(
        members,
        compatibility_score=team.compatibility_score or None,
    )
    return schemas.RiskAnalysisOut(
        team_id=team.id,
        team_name=team.name,
        risks=[schemas.RiskOut(**r) for r in risks],
    )


@router.post("/team/{team_id}/recalculate", response_model=schemas.RiskAnalysisOut)
def recalculate_risk_analysis(team_id: int, db: Session = Depends(get_db)):
    """Persists a human-readable summary onto Team.risk_notes — the field
    the Day 1 ERD reserved for exactly this."""
    team_repo = TeamRepository(db)
    team, members = _load_team_and_members(team_id, db)
    risks = risk_analysis_service.assess_risks(
        members,
        compatibility_score=team.compatibility_score or None,
    )

    team.risk_notes = _format_risk_notes(risks)
    team_repo.save(team)

    return schemas.RiskAnalysisOut(
        team_id=team.id,
        team_name=team.name,
        risks=[schemas.RiskOut(**r) for r in risks],
    )
