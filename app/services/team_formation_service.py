"""
Day 7 — Team Formation Engine.

KMeans/Agglomerative clustering alone groups *similar* people together —
the opposite of what's asked ("balanced candidate teams, not skill-identical
clusters"). So clustering here finds skill **archetypes** across the whole
candidate pool (one archetype per seat in a team — `min(team_size,
candidate_count)` clusters), then each team is built by drawing one member
per archetype, round-robin, across all teams simultaneously. The result:
every team gets a spread of different skill archetypes instead of a pile of
near-duplicates.

Why `archetype_count = min(team_size, candidate_count)`, not something tied
to the number of teams being formed: archetypes represent "seats" — the
goal is one different skill type per team, not one cluster per team. Tying
archetype count to team size is what makes the round-robin assembly
produce diverse teams regardless of how many teams end up being formed.

Why round-robin, not a bin-packing optimizer: a real bin-packing solution
(minimize intra-team similarity variance, say) is more "optimal" but much
harder to explain to a mentor reading the output. The round-robin
assignment is one paragraph to describe and fully deterministic.
"""
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans

from app import models
from app.services import leadership_service
from app.services.matching_service import team_diversity

SUPPORTED_ALGORITHMS = {"kmeans", "agglomerative"}

# Fixed seed so KMeans (which has a random initialization step) produces the
# same clustering for the same input every time — determinism matters here
# since the same candidate pool re-run should yield the same teams.
_KMEANS_RANDOM_STATE = 42


class EmbeddingMissingError(Exception):
    """Raised when one or more candidates have no skill_embedding yet."""

    def __init__(self, intern_ids: list[int]):
        self.intern_ids = list(intern_ids)
        super().__init__(f"Interns missing embeddings: {self.intern_ids}")


class InsufficientCandidatesError(Exception):
    """Raised when fewer than 2 candidates are available to form any team."""


@dataclass
class FormedTeam:
    members: list[models.Intern]
    member_archetypes: dict[int, int]
    suggested_leader_id: int
    diversity_score: float


@dataclass
class TeamFormationResult:
    algorithm: str
    archetype_count: int
    teams: list[FormedTeam]
    unassigned: list[models.Intern]


def _cluster_labels(vectors: np.ndarray, k: int, algorithm: str) -> np.ndarray:
    if algorithm == "kmeans":
        model = KMeans(n_clusters=k, random_state=_KMEANS_RANDOM_STATE, n_init=10)
    elif algorithm == "agglomerative":
        model = AgglomerativeClustering(n_clusters=k)
    else:
        raise ValueError(f"Unknown clustering algorithm: {algorithm!r}")
    return model.fit_predict(vectors)


def _interleave(groups: list[list[models.Intern]]) -> list[models.Intern]:
    """Round-robin flatten: one member from each group in turn, so
    consecutive chunks of the result draw from every archetype."""
    result: list[models.Intern] = []
    max_len = max((len(g) for g in groups), default=0)
    for i in range(max_len):
        for group in groups:
            if i < len(group):
                result.append(group[i])
    return result


def form_teams(
    candidates: list[models.Intern],
    history_by_intern: dict[int, list[models.TeamHistory]],
    team_size: int,
    algorithm: str = "kmeans",
) -> TeamFormationResult:
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm!r}. Supported: {sorted(SUPPORTED_ALGORITHMS)}")

    missing = [c.id for c in candidates if not c.skill_embedding]
    if missing:
        raise EmbeddingMissingError(missing)

    if len(candidates) < 2:
        raise InsufficientCandidatesError(
            "Need at least 2 candidates with embeddings to form any team"
        )

    # Sort for a deterministic, input-order-independent base ordering.
    candidates_sorted = sorted(candidates, key=lambda c: c.id)
    vectors = np.array([c.skill_embedding for c in candidates_sorted], dtype=float)

    archetype_count = min(team_size, len(candidates_sorted))
    labels = _cluster_labels(vectors, archetype_count, algorithm)

    groups: list[list[models.Intern]] = [[] for _ in range(archetype_count)]
    archetype_by_id: dict[int, int] = {}
    for intern, label in zip(candidates_sorted, labels):
        label = int(label)
        groups[label].append(intern)
        archetype_by_id[intern.id] = label

    interleaved = _interleave(groups)

    num_teams = len(candidates_sorted) // team_size if team_size > 0 else 0

    teams: list[FormedTeam] = []
    for i in range(num_teams):
        chunk = interleaved[i * team_size : (i + 1) * team_size]
        leader_entry = leadership_service.suggest_leader(chunk, history_by_intern)
        member_archetypes = {m.id: archetype_by_id[m.id] for m in chunk}
        diversity = team_diversity(chunk)
        teams.append(
            FormedTeam(
                members=chunk,
                member_archetypes=member_archetypes,
                suggested_leader_id=leader_entry["intern_id"],
                diversity_score=round(diversity, 4),
            )
        )

    unassigned = interleaved[num_teams * team_size :]

    return TeamFormationResult(
        algorithm=algorithm,
        archetype_count=archetype_count,
        teams=teams,
        unassigned=unassigned,
    )
