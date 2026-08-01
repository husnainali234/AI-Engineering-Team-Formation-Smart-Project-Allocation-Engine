"""Day 6 — /matching endpoints (Skill Matching Engine)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import matching_service

router = APIRouter(prefix="/matching", tags=["matching"])


def _candidate_to_out(candidate: matching_service.MatchCandidate) -> schemas.MatchCandidateOut:
    return schemas.MatchCandidateOut(
        intern_id=candidate.intern.id,
        full_name=candidate.intern.full_name,
        similarity_score=round(candidate.similarity_score, 4),
        diversity_score=round(candidate.diversity_score, 4),
    )


@router.get("/interns/{intern_id}/recommendations", response_model=list[schemas.MatchCandidateOut])
def teammate_recommendations(
    intern_id: int,
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Ranked teammate recommendations: most similar interns by cosine
    similarity of their skill embeddings."""
    repo = InternRepository(db)
    target = repo.get_by_id_with_skills(intern_id)
    if not target:
        raise HTTPException(status_code=404, detail="Intern not found")

    candidates = repo.list_with_embeddings(exclude_ids=[intern_id])
    try:
        ranked = matching_service.rank_recommendations(target, candidates, limit=limit)
    except matching_service.EmbeddingMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return [_candidate_to_out(c) for c in ranked]


@router.get("/interns/{intern_id}/complementary", response_model=list[schemas.MatchCandidateOut])
def complementary_matches(
    intern_id: int,
    limit: int = Query(default=5, ge=1, le=50),
    min_similarity: float = Query(default=0.3, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """Complementary skill matching: candidates with the least skill overlap
    (highest diversity_score) among those still similar enough in overall
    profile to be a relevant teammate."""
    repo = InternRepository(db)
    target = repo.get_by_id_with_skills(intern_id)
    if not target:
        raise HTTPException(status_code=404, detail="Intern not found")

    candidates = repo.list_with_embeddings(exclude_ids=[intern_id])
    try:
        ranked = matching_service.rank_complementary(target, candidates, limit=limit, min_similarity=min_similarity)
    except matching_service.EmbeddingMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return [_candidate_to_out(c) for c in ranked]


@router.get("/teams/{team_id}/diversity", response_model=schemas.TeamDiversityOut)
def team_skill_diversity(team_id: int, db: Session = Depends(get_db)):
    """0.0-1.0 skill diversity score for an existing team — how little
    overlap there is across all members' skill sets. Same metric
    team_formation_service optimizes for when assembling teams."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    return schemas.TeamDiversityOut(
        team_id=team.id,
        team_name=team.name,
        member_count=len(members),
        diversity_score=round(matching_service.team_diversity(members), 4),
    )
