from app.services import skill_matrix_service
from tests.factories import assign_skill, make_intern, make_skill


def test_technology_frequency_counts_across_structured_and_freetext(db_session):
    react = make_skill(db_session, "React")
    intern_a = make_intern(db_session, technology_stack="Docker", email="a@example.com")
    intern_b = make_intern(db_session, technology_stack="Docker", email="b@example.com")
    intern_c = make_intern(db_session, technology_stack=None, email="c@example.com")
    assign_skill(db_session, intern_a, react, proficiency=3)

    freq = skill_matrix_service.technology_frequency([intern_a, intern_b, intern_c])

    assert freq["Docker"] == 2
    assert freq["React"] == 1


def test_technology_frequency_counts_intern_once_even_if_skill_in_both_sources(db_session):
    react = make_skill(db_session, "React")
    intern = make_intern(db_session, technology_stack="React")
    assign_skill(db_session, intern, react, proficiency=5)

    freq = skill_matrix_service.technology_frequency([intern])

    assert freq["React"] == 1


def test_proficiency_aggregation_only_covers_structured_skills(db_session):
    react = make_skill(db_session, "React")
    intern_a = make_intern(db_session, technology_stack=None, email="a@example.com")
    intern_b = make_intern(db_session, technology_stack=None, email="b@example.com")
    assign_skill(db_session, intern_a, react, proficiency=2)
    assign_skill(db_session, intern_b, react, proficiency=4)

    agg = skill_matrix_service.proficiency_aggregation([intern_a, intern_b])

    assert agg["React"]["avg_proficiency"] == 3.0
    assert agg["React"]["min_proficiency"] == 2
    assert agg["React"]["max_proficiency"] == 4
    assert agg["React"]["rated_intern_count"] == 2


def test_build_skill_matrix_merges_frequency_and_proficiency(db_session):
    react = make_skill(db_session, "React")
    intern_a = make_intern(db_session, technology_stack="Docker", email="a@example.com")
    intern_b = make_intern(db_session, technology_stack=None, email="b@example.com")
    assign_skill(db_session, intern_a, react, proficiency=3)
    assign_skill(db_session, intern_b, react, proficiency=5)

    matrix = {row["skill_name"]: row for row in skill_matrix_service.build_skill_matrix([intern_a, intern_b])}

    assert matrix["React"]["intern_count"] == 2
    assert matrix["React"]["avg_proficiency"] == 4.0
    assert matrix["Docker"]["intern_count"] == 1
    # Docker only came from technology_stack -> no proficiency data
    assert matrix["Docker"]["avg_proficiency"] is None


def test_build_skill_matrix_is_sorted_most_common_first(db_session):
    react = make_skill(db_session, "React")
    docker = make_skill(db_session, "Docker")
    intern_a = make_intern(db_session, technology_stack=None, email="a@example.com")
    intern_b = make_intern(db_session, technology_stack=None, email="b@example.com")
    intern_c = make_intern(db_session, technology_stack=None, email="c@example.com")
    for intern in (intern_a, intern_b, intern_c):
        assign_skill(db_session, intern, react, proficiency=3)
    assign_skill(db_session, intern_a, docker, proficiency=3)

    rows = skill_matrix_service.build_skill_matrix([intern_a, intern_b, intern_c])

    assert rows[0]["skill_name"] == "React"
    assert rows[0]["intern_count"] == 3


def test_build_skill_matrix_empty_team_returns_empty_list():
    assert skill_matrix_service.build_skill_matrix([]) == []
