import pytest

from app.services import team_formation_service
from tests.factories import make_intern


def _intern_with_embedding(db, email, vector, **overrides):
    intern = make_intern(db, email=email, **overrides)
    intern.skill_embedding = vector
    db.add(intern)
    db.commit()
    db.refresh(intern)
    return intern


def test_form_teams_raises_on_missing_embeddings(db_session):
    a = make_intern(db_session, email="a@example.com")
    b = _intern_with_embedding(db_session, "b@example.com", [1.0, 0.0])
    with pytest.raises(team_formation_service.EmbeddingMissingError) as exc_info:
        team_formation_service.form_teams([a, b], history_by_intern={}, team_size=2)
    assert a.id in exc_info.value.intern_ids


def test_form_teams_raises_with_fewer_than_two_candidates(db_session):
    a = _intern_with_embedding(db_session, "a@example.com", [1.0, 0.0])
    with pytest.raises(team_formation_service.InsufficientCandidatesError):
        team_formation_service.form_teams([a], history_by_intern={}, team_size=2)


def test_form_teams_rejects_unknown_algorithm(db_session):
    a = _intern_with_embedding(db_session, "a@example.com", [1.0, 0.0])
    b = _intern_with_embedding(db_session, "b@example.com", [0.0, 1.0])
    with pytest.raises(ValueError):
        team_formation_service.form_teams([a, b], history_by_intern={}, team_size=2, algorithm="neo4j")


@pytest.mark.parametrize("algorithm", ["kmeans", "agglomerative"])
def test_form_teams_assigns_every_candidate_when_evenly_divisible(db_session, algorithm):
    vectors = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9], [1.0, 1.0], [0.9, 0.9], [-1.0, 0.0], [0.0, -1.0]]
    interns = [
        _intern_with_embedding(db_session, f"i{i}@example.com", v, full_name=f"Intern {i}")
        for i, v in enumerate(vectors)
    ]
    result = team_formation_service.form_teams(interns, history_by_intern={}, team_size=4, algorithm=algorithm)
    assert result.algorithm == algorithm
    assert result.unassigned == []
    assert sum(len(t.members) for t in result.teams) == len(interns)
    for team in result.teams:
        assert len(team.members) <= 4
        assert team.suggested_leader_id in {m.id for m in team.members}


def test_form_teams_leaves_remainder_unassigned(db_session):
    vectors = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]]
    interns = [_intern_with_embedding(db_session, f"r{i}@example.com", v) for i, v in enumerate(vectors)]
    result = team_formation_service.form_teams(interns, history_by_intern={}, team_size=2)
    assert sum(len(t.members) for t in result.teams) + len(result.unassigned) == len(interns)
    for team in result.teams:
        assert len(team.members) <= 2


def test_form_teams_is_deterministic(db_session):
    vectors = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9], [1.0, 1.0], [0.9, 0.9]]
    interns = [_intern_with_embedding(db_session, f"d{i}@example.com", v) for i, v in enumerate(vectors)]
    result_a = team_formation_service.form_teams(interns, history_by_intern={}, team_size=3)
    result_b = team_formation_service.form_teams(interns, history_by_intern={}, team_size=3)
    ids_a = [[m.id for m in t.members] for t in result_a.teams]
    ids_b = [[m.id for m in t.members] for t in result_b.teams]
    assert ids_a == ids_b
