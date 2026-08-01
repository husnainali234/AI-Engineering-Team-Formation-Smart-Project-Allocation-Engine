import pytest

from app.services import matching_service
from tests.factories import assign_skill, make_intern, make_skill


def test_cosine_similarity_identical_vectors_is_one():
    v = [1.0, 0.0, 0.0]
    assert matching_service.cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert matching_service.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_opposite_vectors_is_negative_one():
    assert matching_service.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_similarity_handles_zero_vector():
    assert matching_service.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_rank_recommendations_raises_when_target_has_no_embedding(db_session):
    target = make_intern(db_session, email="target@example.com")
    candidate = make_intern(db_session, email="candidate@example.com")
    candidate.skill_embedding = [1.0, 0.0]

    with pytest.raises(matching_service.EmbeddingMissingError):
        matching_service.rank_recommendations(target, [candidate])


def test_rank_recommendations_orders_by_similarity_descending(db_session):
    target = make_intern(db_session, email="target@example.com")
    target.skill_embedding = [1.0, 0.0]

    close = make_intern(db_session, email="close@example.com")
    close.skill_embedding = [0.9, 0.1]

    far = make_intern(db_session, email="far@example.com")
    far.skill_embedding = [0.0, 1.0]

    ranked = matching_service.rank_recommendations(target, [far, close], limit=5)

    assert [c.intern.id for c in ranked] == [close.id, far.id]


def test_rank_recommendations_excludes_candidates_without_embeddings(db_session):
    target = make_intern(db_session, email="target@example.com")
    target.skill_embedding = [1.0, 0.0]

    no_embedding = make_intern(db_session, email="none@example.com")  # skill_embedding stays None

    ranked = matching_service.rank_recommendations(target, [no_embedding])

    assert ranked == []


def test_rank_recommendations_respects_limit(db_session):
    target = make_intern(db_session, email="target@example.com")
    target.skill_embedding = [1.0, 0.0]

    candidates = []
    for i in range(5):
        c = make_intern(db_session, email=f"c{i}@example.com")
        c.skill_embedding = [1.0 - i * 0.01, 0.01 * i]
        candidates.append(c)

    ranked = matching_service.rank_recommendations(target, candidates, limit=2)

    assert len(ranked) == 2


def test_rank_complementary_filters_by_min_similarity_and_sorts_by_diversity(db_session):
    react = make_skill(db_session, "React")
    django = make_skill(db_session, "Django")

    target = make_intern(db_session, email="target@example.com", technology_stack=None)
    assign_skill(db_session, target, react, proficiency=4)
    target.skill_embedding = [1.0, 0.0]

    similar_but_redundant = make_intern(db_session, email="redundant@example.com", technology_stack=None)
    assign_skill(db_session, similar_but_redundant, react, proficiency=3)
    similar_but_redundant.skill_embedding = [0.95, 0.05]  # high similarity, same skill -> low diversity

    similar_and_complementary = make_intern(db_session, email="complement@example.com", technology_stack=None)
    assign_skill(db_session, similar_and_complementary, django, proficiency=3)
    similar_and_complementary.skill_embedding = [0.9, 0.1]  # still similar enough, different skill -> high diversity

    too_different = make_intern(db_session, email="different@example.com", technology_stack=None)
    assign_skill(db_session, too_different, django, proficiency=5)
    too_different.skill_embedding = [0.0, 1.0]  # below min_similarity -> excluded entirely

    ranked = matching_service.rank_complementary(
        target,
        [similar_but_redundant, similar_and_complementary, too_different],
        min_similarity=0.5,
    )

    ranked_ids = [c.intern.id for c in ranked]
    assert too_different.id not in ranked_ids
    assert ranked_ids[0] == similar_and_complementary.id


def test_team_diversity_empty_team_is_zero():
    assert matching_service.team_diversity([]) == 0.0


def test_team_diversity_no_overlap_is_one(db_session):
    react = make_skill(db_session, "React")
    django = make_skill(db_session, "Django")
    a = make_intern(db_session, email="a@example.com", technology_stack=None)
    b = make_intern(db_session, email="b@example.com", technology_stack=None)
    assign_skill(db_session, a, react, proficiency=3)
    assign_skill(db_session, b, django, proficiency=3)

    assert matching_service.team_diversity([a, b]) == 1.0
