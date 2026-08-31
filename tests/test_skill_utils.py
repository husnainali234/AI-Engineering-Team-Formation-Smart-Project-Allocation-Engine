from app.services.skill_utils import (
    group_diversity_score,
    intern_proficiency_map,
    intern_skill_names,
    skill_diversity_score,
)
from tests.factories import assign_skill, make_intern, make_skill


def test_intern_skill_names_combines_structured_and_freetext(db_session):
    intern = make_intern(db_session, technology_stack="React, Docker")
    skill = make_skill(db_session, "Python")
    assign_skill(db_session, intern, skill, proficiency=4)

    names = intern_skill_names(intern)

    assert names == {"React", "Docker", "Python"}


def test_intern_skill_names_dedupes_when_same_tech_in_both_sources(db_session):
    intern = make_intern(db_session, technology_stack="React")
    skill = make_skill(db_session, "React", category="Framework")
    assign_skill(db_session, intern, skill, proficiency=5)

    assert intern_skill_names(intern) == {"React"}


def test_intern_skill_names_handles_no_data(db_session):
    intern = make_intern(db_session, technology_stack=None, project_interests=None)
    assert intern_skill_names(intern) == set()


def test_intern_proficiency_map_only_uses_structured_skills(db_session):
    intern = make_intern(db_session, technology_stack="Vue.js")  # no proficiency data
    skill = make_skill(db_session, "FastAPI")
    assign_skill(db_session, intern, skill, proficiency=2)

    proficiencies = intern_proficiency_map(intern)

    assert proficiencies == {"FastAPI": 2}
    assert "Vue.js" not in proficiencies


def test_skill_diversity_score_identical_sets_is_half():
    assert skill_diversity_score({"React", "Node.js"}, {"React", "Node.js"}) == 0.5


def test_skill_diversity_score_disjoint_sets_is_one():
    assert skill_diversity_score({"React"}, {"Django"}) == 1.0


def test_skill_diversity_score_empty_sets_is_zero():
    assert skill_diversity_score(set(), set()) == 0.0


def test_skill_diversity_score_partial_overlap():
    # A={React,Node,Docker} B={React,Django} -> union=4, total=5 -> 0.8
    score = skill_diversity_score({"React", "Node.js", "Docker"}, {"React", "Django"})
    assert score == 0.8


def test_group_diversity_score_generalizes_pairwise_case():
    score = group_diversity_score([{"React", "Node.js"}, {"React", "Django"}, {"Docker"}])
    # union = {React, Node.js, Django, Docker} = 4; total = 2+2+1 = 5
    assert score == 4 / 5


def test_group_diversity_score_all_empty_is_zero():
    assert group_diversity_score([set(), set()]) == 0.0
