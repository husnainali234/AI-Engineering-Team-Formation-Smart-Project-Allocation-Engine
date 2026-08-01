import pytest

from app.services import project_recommendation_service
from tests.factories import make_intern, make_project


def test_score_project_fit_full_coverage(db_session):
    intern = make_intern(db_session, email="pf1@example.com", technology_stack="Laravel, MySQL, Vue")
    project = make_project(db_session, title="Laravel CMS", required_tech_stack="Laravel, MySQL, Vue")
    fit = project_recommendation_service.score_project_fit({"Laravel", "MySQL", "Vue"}, project)
    assert fit["coverage_score"] == 1.0
    assert fit["missing_skills"] == []
    assert set(fit["matched_skills"]) == {"Laravel", "MySQL", "Vue"}


def test_score_project_fit_partial_coverage(db_session):
    project = make_project(db_session, title="MERN App", required_tech_stack="MongoDB, Express, React, Node.js")
    fit = project_recommendation_service.score_project_fit({"React", "Node.js"}, project)
    assert fit["coverage_score"] == pytest.approx(0.5)
    assert set(fit["missing_skills"]) == {"MongoDB", "Express"}


def test_score_project_fit_is_case_insensitive(db_session):
    project = make_project(db_session, title="React App", required_tech_stack="react, NODE.JS")
    fit = project_recommendation_service.score_project_fit({"React", "Node.js"}, project)
    assert fit["coverage_score"] == 1.0


def test_score_project_fit_handles_no_required_skills(db_session):
    project = make_project(db_session, title="Undefined Project", required_tech_stack="")
    fit = project_recommendation_service.score_project_fit({"React"}, project)
    assert fit["coverage_score"] == 0.0
    assert fit["required_skill_count"] == 0


def test_team_skill_set_unions_all_members(db_session):
    a = make_intern(db_session, email="union1@example.com", technology_stack="React")
    b = make_intern(db_session, email="union2@example.com", technology_stack="Django")
    assert project_recommendation_service.team_skill_set([a, b]) == {"React", "Django"}


def test_recommend_projects_ranks_highest_coverage_first(db_session):
    a = make_intern(db_session, email="rec1@example.com", technology_stack="Laravel, MySQL")
    b = make_intern(db_session, email="rec2@example.com", technology_stack="Vue")
    laravel_project = make_project(db_session, title="Laravel Shop", required_tech_stack="Laravel, MySQL, Vue")
    unrelated_project = make_project(db_session, title="ML Pipeline", required_tech_stack="Python, TensorFlow")
    ranked = project_recommendation_service.recommend_projects([a, b], [unrelated_project, laravel_project])
    assert ranked[0]["title"] == "Laravel Shop"
    assert ranked[0]["coverage_score"] == 1.0
