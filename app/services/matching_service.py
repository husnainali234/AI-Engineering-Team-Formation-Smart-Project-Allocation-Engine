"""
Day 6 — Skill Matching Engine.

Ranks candidate teammates for a given intern using cosine similarity between
their sentence-transformer skill embeddings (Day 4), plus a complementary
variant that favors low skill overlap instead of high similarity, and a
skill diversity score usable for both pairs and whole teams.
"""
from dataclasses import dataclass

import numpy as np

from app import models
from app.services.skill_utils import group_diversity_score, intern_skill_names, skill_diversity_score


class EmbeddingMissingError(Exception):
    """Raised when the intern being matched against has no embedding yet —
    the caller should generate one (POST /embeddings/interns/{id}/generate)
    before matching."""


@dataclass
class MatchCandidate:
    intern: models.Intern
    similarity_score: float
    diversity_score: float


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    a = np.asarray(vector_a, dtype=float)
    b = np.asarray(vector_b, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _require_embedding(intern: models.Intern) -> list[float]:
    if not intern.skill_embedding:
        raise EmbeddingMissingError(
            f"Intern {intern.id} has no embedding yet — "
            f"POST /embeddings/interns/{intern.id}/generate first."
        )
    return intern.skill_embedding


def _score_candidates(target: models.Intern, candidates: list[models.Intern]) -> list[MatchCandidate]:
    target_vector = _require_embedding(target)
    target_skills = intern_skill_names(target)

    scored = []
    for candidate in candidates:
        if candidate.id == target.id or not candidate.skill_embedding:
            continue
        similarity = cosine_similarity(target_vector, candidate.skill_embedding)
        diversity = skill_diversity_score(target_skills, intern_skill_names(candidate))
        scored.append(MatchCandidate(intern=candidate, similarity_score=similarity, diversity_score=diversity))
    return scored


def rank_recommendations(target: models.Intern, candidates: list[models.Intern], limit: int = 5) -> list[MatchCandidate]:
    """Ranked teammate recommendations: candidates most similar in overall
    skill/interest profile to the target intern, using cosine similarity of
    their sentence-transformer embeddings."""
    scored = _score_candidates(target, candidates)
    scored.sort(key=lambda c: c.similarity_score, reverse=True)
    return scored[:limit]


def rank_complementary(
    target: models.Intern,
    candidates: list[models.Intern],
    limit: int = 5,
    min_similarity: float = 0.3,
) -> list[MatchCandidate]:
    """Complementary skill matching: candidates whose skill set overlaps the
    *least* with the target's (highest diversity_score) — i.e. who'd fill
    gaps rather than duplicate strengths — while still requiring a minimum
    embedding similarity so results stay in a related problem domain
    (someone with an entirely unrelated profile isn't a useful complement,
    just an unrelated teammate)."""
    scored = [c for c in _score_candidates(target, candidates) if c.similarity_score >= min_similarity]
    scored.sort(key=lambda c: c.diversity_score, reverse=True)
    return scored[:limit]


def team_diversity(team_members: list[models.Intern]) -> float:
    """Skill diversity score (0.0-1.0) for a whole team: how little overlap
    there is across all members' skill sets. See
    app.services.skill_utils.group_diversity_score for the formula."""
    return group_diversity_score([intern_skill_names(m) for m in team_members])
