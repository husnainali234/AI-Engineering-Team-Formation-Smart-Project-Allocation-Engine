"""Day 7 — /team-formation endpoints (Team Formation Engine)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import team_formation_service


router = APIRouter(prefix="/team-formation", tags=["team-formation"])


def _resolve_candidates(request: schemas.TeamFormationRequest, intern_repo: InternRepository) -> list[models.Intern]:
    if request.intern_ids:
        candidates = intern_repo.list_by_ids(request.intern_ids)
        found_ids = {c.id for c in candidates}
        missing = [i for i in request.intern_ids if i not in found_ids]
        if missing:
            raise HTTPException(status_code=404, detail=f"Unknown intern_ids: {missing}")
        return candidates
    # Default candidate pool: interns with an embedding, marked available,
    # and not already on a team — so re-running formation never
    # double-books someone.
    return intern_repo.list_available_unassigned_with_embeddings()


def _history_by_intern(team_repo: TeamRepository, candidates: list[models.Intern]) -> dict[int, list]:
    if not candidates:
        return {}
    history_by_intern: dict[int, list] = {}
    for h in team_repo.team_history_for_interns([c.id for c in candidates]):
        history_by_intern.setdefault(h.intern_id, []).append(h)
    return history_by_intern


def _run_formation(request: schemas.TeamFormationRequest, db: Session) -> team_formation_service.TeamFormationResult:
    intern_repo = InternRepository(db)
    team_repo = TeamRepository(db)
    candidates = _resolve_candidates(request, intern_repo)

    try:
        return team_formation_service.form_teams(
            candidates,
            history_by_intern=_history_by_intern(team_repo, candidates),
            team_size=request.team_size,
            algorithm=request.algorithm,
        )
    except team_formation_service.InsufficientCandidatesError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except team_formation_service.EmbeddingMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


def _formed_team_to_schema(team, team_index: int, persisted=None) -> schemas.FormedTeamOut:
    members_out = [
        schemas.FormedTeamMemberOut(
            intern_id=member.id,
            full_name=member.full_name,
            role="Lead" if member.id == team.suggested_leader_id else "Member",
            skill_archetype=team.member_archetypes[member.id],
        )
        for member in team.members
    ]
    leader = next(m for m in team.members if m.id == team.suggested_leader_id)

    return schemas.FormedTeamOut(
        id=persisted.id if persisted else None,
        name=persisted.name if persisted else None,
        team_index=team_index,
        members=members_out,
        suggested_leader_intern_id=team.suggested_leader_id,
        suggested_leader_name=leader.full_name,
        diversity_score=team.diversity_score,
    )


@router.post("/preview", response_model=schemas.TeamFormationResultOut)
def preview_team_formation(request: schemas.TeamFormationRequest, db: Session = Depends(get_db)):
    """Dry run — never writes to the DB."""
    result = _run_formation(request, db)

    return schemas.TeamFormationResultOut(
        algorithm=result.algorithm,
        archetype_count=result.archetype_count,
        teams=[_formed_team_to_schema(t, i) for i, t in enumerate(result.teams)],
        unassigned_intern_ids=[i.id for i in result.unassigned],
    )


@router.post("/commit", response_model=schemas.TeamFormationResultOut)
def commit_team_formation(request: schemas.TeamFormationRequest, db: Session = Depends(get_db)):
    """Same computation as /preview, but persists real Team + TeamMember
    rows (role 'Lead' for the suggested leader)."""
    result = _run_formation(request, db)

    persisted_pairs = []
    for i, team in enumerate(result.teams):
        db_team = models.Team(name=f"Auto-Formed Team {i + 1}")
        db.add(db_team)
        db.flush()
        for member in team.members:
            role = "Lead" if member.id == team.suggested_leader_id else "Member"
            db.add(models.TeamMember(team_id=db_team.id, intern_id=member.id, role=role))
        db.commit()
        db.refresh(db_team)
        persisted_pairs.append((db_team, team))

    return schemas.TeamFormationResultOut(
        algorithm=result.algorithm,
        archetype_count=result.archetype_count,
        teams=[_formed_team_to_schema(t, i, persisted=db_team) for i, (db_team, t) in enumerate(persisted_pairs)],
        unassigned_intern_ids=[i.id for i in result.unassigned],
    )
