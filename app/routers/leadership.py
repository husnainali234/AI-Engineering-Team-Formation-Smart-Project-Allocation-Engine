"""Day 7 — /leadership endpoints (hybrid rule-based Leadership Detection)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import leadership_service

router = APIRouter(prefix="/leadership", tags=["leadership"])


def _history_by_intern(team_repo: TeamRepository, member_ids: list[int]) -> dict[int, list[models.TeamHistory]]:
    history_by_intern: dict[int, list[models.TeamHistory]] = {}
    for h in team_repo.team_history_for_interns(member_ids):
        history_by_intern.setdefault(h.intern_id, []).append(h)
    return history_by_intern


@router.get("/interns/{intern_id}/score", response_model=schemas.LeadershipScoreOut)
def intern_leadership_score(intern_id: int, db: Session = Depends(get_db)):
    """One intern's leadership score breakdown (leadership_score,
    communication, team history, contribution consistency), independent
    of any team — used by /leadership/team/{id}/suggest under the hood."""
    intern = InternRepository(db).get_by_id(intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")

    team_repo = TeamRepository(db)
    history = team_repo.team_history_for_interns([intern_id])
    result = leadership_service.score_leadership(intern, history)

    return schemas.LeadershipScoreOut(
        intern_id=intern.id,
        full_name=intern.full_name,
        total_score=result["total_score"],
        components=result["components"],
    )


@router.get("/team/{team_id}/suggest", response_model=schemas.TeamLeadershipSuggestionOut)
def suggest_team_leader(team_id: int, db: Session = Depends(get_db)):
    """Read-only, like Day 6's GET /compatibility/team/{id} — doesn't write
    anything. Returns the full ranking plus which member the engine
    suggests."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    if not members:
        raise HTTPException(status_code=409, detail="Team has no members")

    history_by_intern = _history_by_intern(TeamRepository(db), [m.id for m in members])
    ranking = leadership_service.rank_leadership(members, history_by_intern)
    leader = ranking[0]

    return schemas.TeamLeadershipSuggestionOut(
        team_id=team.id,
        team_name=team.name,
        suggested_leader_intern_id=leader["intern_id"],
        suggested_leader_name=leader["full_name"],
        ranking=[schemas.LeadershipRankingEntryOut(**r) for r in ranking],
    )


@router.post("/team/{team_id}/apply", response_model=schemas.TeamLeadershipSuggestionOut)
def apply_team_leader(team_id: int, db: Session = Depends(get_db)):
    """Sets the top-ranked member's TeamMember.role to 'Lead', everyone
    else to 'Member'."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    if not members:
        raise HTTPException(status_code=409, detail="Team has no members")

    history_by_intern = _history_by_intern(TeamRepository(db), [m.id for m in members])
    ranking = leadership_service.rank_leadership(members, history_by_intern)
    leader_id = ranking[0]["intern_id"]

    team_member_rows = db.query(models.TeamMember).filter(models.TeamMember.team_id == team_id).all()
    for tm in team_member_rows:
        tm.role = "Lead" if tm.intern_id == leader_id else "Member"
        db.add(tm)
    db.commit()

    return schemas.TeamLeadershipSuggestionOut(
        team_id=team.id,
        team_name=team.name,
        suggested_leader_intern_id=leader_id,
        suggested_leader_name=ranking[0]["full_name"],
        ranking=[schemas.LeadershipRankingEntryOut(**r) for r in ranking],
    )
