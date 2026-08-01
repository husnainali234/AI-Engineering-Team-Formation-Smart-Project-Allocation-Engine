import pytest

from app.services import compatibility_service
from tests.factories import make_intern, make_team


def test_weights_sum_to_one():
    assert sum(compatibility_service.COMPATIBILITY_WEIGHTS.values()) == pytest.approx(1.0)


def test_pairwise_compatibility_returns_full_breakdown(db_session):
    a = make_intern(db_session, email="a@example.com", communication_score=8, leadership_score=7,
                     attendance_pct=95, github_contributions=100)
    b = make_intern(db_session, email="b@example.com", communication_score=8, leadership_score=7,
                     attendance_pct=95, github_contributions=100)

    result = compatibility_service.pairwise_compatibility(a, b, [], [])

    assert set(result["components"].keys()) == set(compatibility_service.COMPATIBILITY_WEIGHTS.keys())
    assert 0 <= result["total_score"] <= 100


def test_identical_high_scoring_interns_score_higher_than_mismatched(db_session):
    strong_a = make_intern(db_session, email="sa@example.com", communication_score=9, leadership_score=9,
                            attendance_pct=98, github_contributions=150)
    strong_b = make_intern(db_session, email="sb@example.com", communication_score=9, leadership_score=9,
                            attendance_pct=98, github_contributions=150)

    weak = make_intern(db_session, email="w@example.com", communication_score=1, leadership_score=1,
                        attendance_pct=50, github_contributions=0)

    good_pair = compatibility_service.pairwise_compatibility(strong_a, strong_b, [], [])
    mismatched_pair = compatibility_service.pairwise_compatibility(strong_a, weak, [], [])

    assert good_pair["total_score"] > mismatched_pair["total_score"]


def test_team_history_component_neutral_with_no_shared_history(db_session):
    a = make_intern(db_session, email="a@example.com")
    b = make_intern(db_session, email="b@example.com")

    result = compatibility_service.pairwise_compatibility(a, b, [], [])

    assert result["components"]["team_history"]["raw_score"] == 0.5


def test_team_history_component_reflects_shared_positive_outcome(db_session):
    from app import models

    a = make_intern(db_session, email="a@example.com")
    b = make_intern(db_session, email="b@example.com")

    history_a = [models.TeamHistory(intern_id=a.id, past_team_name="Falcons", outcome_rating=9.0)]
    history_b = [models.TeamHistory(intern_id=b.id, past_team_name="Falcons", outcome_rating=9.0)]

    result = compatibility_service.pairwise_compatibility(a, b, history_a, history_b)

    assert result["components"]["team_history"]["raw_score"] == pytest.approx(0.9)


def test_github_activity_saturates_at_cap(db_session):
    a = make_intern(db_session, email="a@example.com", github_contributions=1000)
    b = make_intern(db_session, email="b@example.com", github_contributions=1000)

    result = compatibility_service.pairwise_compatibility(a, b, [], [])

    assert result["components"]["github_activity"]["raw_score"] == 1.0


def test_team_compatibility_averages_all_pairs(db_session):
    a = make_intern(db_session, email="a@example.com")
    b = make_intern(db_session, email="b@example.com")
    c = make_intern(db_session, email="c@example.com")

    result = compatibility_service.team_compatibility([a, b, c], {})

    assert result["member_count"] == 3
    assert len(result["pairs"]) == 3  # C(3,2)
    expected_avg = round(sum(p["total_score"] for p in result["pairs"]) / 3, 2)
    assert result["average_score"] == expected_avg


def test_team_compatibility_single_member_has_no_pairs(db_session):
    a = make_intern(db_session, email="a@example.com")
    result = compatibility_service.team_compatibility([a], {})
    assert result["pairs"] == []
    assert result["average_score"] == 0.0
