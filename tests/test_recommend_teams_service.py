import pytest

from app.services import recommend_teams_service
from tests.factories import make_intern, make_project


def test_compute_team_recommendation_returns_all_components(db_session):
    a = make_intern(
        db_session, email="rt1@example.com", technology_stack="Laravel, MySQL",
        attendance_pct=90.0, leadership_score=8.0, communication_score=8.0,
    )
    b = make_intern(
        db_session, email="rt2@example.com", technology_stack="Vue",
        attendance_pct=85.0, leadership_score=6.0, communication_score=7.0,
    )
    project = make_project(db_session, title="Laravel Shop", required_tech_stack="Laravel, MySQL, Vue")

    result = recommend_teams_service.compute_team_recommendation(
        [a, b], history_by_intern={}, feedback_by_intern={}, projects=[project],
    )

    assert 0.0 <= result["compatibility_score"] <= 100.0
    assert result["skill_matrix"]
    assert result["project_fit"]["title"] == "Laravel Shop"
    assert result["project_fit"]["coverage_score"] == 1.0
    assert 0.0 <= result["success_probability"] <= 100.0
    assert isinstance(result["risks"], list)
    assert 0.0 <= result["overall_score"] <= 100.0


def test_compute_team_recommendation_handles_no_projects(db_session):
    a = make_intern(db_session, email="rt3@example.com")
    b = make_intern(db_session, email="rt4@example.com")

    result = recommend_teams_service.compute_team_recommendation(
        [a, b], history_by_intern={}, feedback_by_intern={}, projects=[],
    )

    assert result["project_fit"] is None
    assert 0.0 <= result["overall_score"] <= 100.0


def test_overall_score_weights_sum_to_one():
    assert sum(recommend_teams_service.OVERALL_SCORE_WEIGHTS.values()) == pytest.approx(1.0)


def test_overall_score_rewards_stronger_signals(db_session):
    strong_a = make_intern(
        db_session, email="rt5@example.com", technology_stack="React, Node.js",
        attendance_pct=98.0, leadership_score=9.0, communication_score=9.0,
    )
    strong_b = make_intern(
        db_session, email="rt6@example.com", technology_stack="MongoDB, Express",
        attendance_pct=97.0, leadership_score=8.0, communication_score=8.0,
    )
    project = make_project(db_session, title="MERN App", required_tech_stack="React, Node.js, MongoDB, Express")
    strong_result = recommend_teams_service.compute_team_recommendation(
        [strong_a, strong_b], history_by_intern={}, feedback_by_intern={}, projects=[project],
    )

    weak_a = make_intern(
        db_session, email="rt7@example.com", technology_stack="React",
        attendance_pct=40.0, leadership_score=1.0, communication_score=1.0,
    )
    weak_b = make_intern(
        db_session, email="rt8@example.com", technology_stack="React",
        attendance_pct=35.0, leadership_score=1.0, communication_score=1.0,
    )
    weak_result = recommend_teams_service.compute_team_recommendation(
        [weak_a, weak_b], history_by_intern={}, feedback_by_intern={}, projects=[project],
    )

    assert strong_result["overall_score"] > weak_result["overall_score"]
