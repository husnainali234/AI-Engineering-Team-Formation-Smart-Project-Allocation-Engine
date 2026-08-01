"""
Day 6 — /recommendations endpoint.

Distinct from /matching (pure embedding similarity or pure diversity) and
/compatibility (pairwise score for a *given* pair): this is the "who should
this intern actually team up with" endpoint, blending both engines into one
ranked list — the Recommendation API called for in the Day 6 spec.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import compatibility_service, matching_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

# How much weight embedding similarity vs. compatibility score gets in the
# blended ranking. Similarity says "similar skillset"; compatibility says
# "would work well together" — recommendations should reflect the latter
# proportionally more, since it also incorporates skill diversity already.
SIMILARITY_WEIGHT = 0.4
COMPATIBILITY_WEIGHT = 0.6


@router.get("/interns/{intern_id}", response_model=list[schemas.RecommendationOut])
def recommend_teammates(
    intern_id: int,
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Ranked teammate recommendations blending embedding similarity (Day 6
    matching) and pairwise Compatibility Score (Day 6 compatibility) —
    "who should this intern actually team up with", as distinct from
    /matching's pure-similarity or pure-diversity views."""
    intern_repo = InternRepository(db)
    target = intern_repo.get_by_id_with_skills(intern_id)
    if not target:
        raise HTTPException(status_code=404, detail="Intern not found")

    candidates = intern_repo.list_with_embeddings(exclude_ids=[intern_id])
    try:
        # Score every candidate with an embedding, not just the top-N by
        # similarity, so a high-compatibility/lower-similarity candidate can
        # still surface in the blended ranking.
        scored = matching_service.rank_recommendations(target, candidates, limit=len(candidates))
    except matching_service.EmbeddingMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    team_repo = TeamRepository(db)
    target_history = team_repo.team_history_for_interns([intern_id])

    results = []
    for candidate in scored:
        candidate_history = team_repo.team_history_for_interns([candidate.intern.id])
        compat = compatibility_service.pairwise_compatibility(
            target, candidate.intern, target_history, candidate_history
        )
        compatibility_score = compat["total_score"]
        blended = (
            SIMILARITY_WEIGHT * candidate.similarity_score
            + COMPATIBILITY_WEIGHT * (compatibility_score / 100.0)
        )
        results.append(
            schemas.RecommendationOut(
                intern_id=candidate.intern.id,
                full_name=candidate.intern.full_name,
                similarity_score=round(candidate.similarity_score, 4),
                diversity_score=round(candidate.diversity_score, 4),
                compatibility_score=compatibility_score,
                blended_rank_score=round(blended, 4),
            )
        )

    results.sort(key=lambda r: r.blended_rank_score, reverse=True)
    return results[:limit]
