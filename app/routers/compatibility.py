"""Day 6 — /compatibility endpoints (Compatibility Score engine)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import compatibility_service

router = APIRouter(prefix="/compatibility", tags=["compatibility"])


@router.get("/pair", response_model=schemas.PairwiseCompatibilityOut)
def pairwise_compatibility(intern_a_id: int, intern_b_id: int, db: Session = Depends(get_db)):
    """Compatibility Score for one specific pair of interns (not
    necessarily on the same team) — the six-signal weighted breakdown,
    with each component's raw score, weight, and contribution."""
    if intern_a_id == intern_b_id:
        raise HTTPException(status_code=422, detail="intern_a_id and intern_b_id must be different interns")

    intern_repo = InternRepository(db)
    intern_a = intern_repo.get_by_id_with_skills(intern_a_id)
    intern_b = intern_repo.get_by_id_with_skills(intern_b_id)
    if not intern_a or not intern_b:
        raise HTTPException(status_code=404, detail="One or both interns not found")

    team_repo = TeamRepository(db)
    history_a = team_repo.team_history_for_interns([intern_a_id])
    history_b = team_repo.team_history_for_interns([intern_b_id])

    result = compatibility_service.pairwise_compatibility(intern_a, intern_b, history_a, history_b)
    return schemas.PairwiseCompatibilityOut(**result)


@router.get("/team/{team_id}", response_model=schemas.TeamCompatibilityOut)
def team_compatibility(team_id: int, db: Session = Depends(get_db)):
    """Average pairwise compatibility across every member pair on the team,
    with each pair's breakdown included."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    team_repo = TeamRepository(db)
    history_by_intern = {}
    if members:
        all_history = team_repo.team_history_for_interns([m.id for m in members])
        for h in all_history:
            history_by_intern.setdefault(h.intern_id, []).append(h)

    result = compatibility_service.team_compatibility(members, history_by_intern)

    return schemas.TeamCompatibilityOut(
        team_id=team.id,
        team_name=team.name,
        member_count=result["member_count"],
        average_score=result["average_score"],
        pairs=[schemas.PairwiseCompatibilityOut(**p) for p in result["pairs"]],
    )


@router.post("/team/{team_id}/recalculate", response_model=schemas.TeamCompatibilityOut)
def recalculate_team_compatibility(team_id: int, db: Session = Depends(get_db)):
    """Same computation as GET /compatibility/team/{id}, but also persists
    the resulting average onto Team.compatibility_score — the field Day 1's
    ERD reserved for exactly this ('from Collaboration Prediction Model')."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    team_repo = TeamRepository(db)
    history_by_intern = {}
    if members:
        all_history = team_repo.team_history_for_interns([m.id for m in members])
        for h in all_history:
            history_by_intern.setdefault(h.intern_id, []).append(h)

    result = compatibility_service.team_compatibility(members, history_by_intern)

    team.compatibility_score = result["average_score"]
    team_repo.save(team)

    return schemas.TeamCompatibilityOut(
        team_id=team.id,
        team_name=team.name,
        member_count=result["member_count"],
        average_score=result["average_score"],
        pairs=[schemas.PairwiseCompatibilityOut(**p) for p in result["pairs"]],
    )
