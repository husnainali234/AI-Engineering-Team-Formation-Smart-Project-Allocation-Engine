import pytest

from app import models
from app.services import leadership_service
from tests.factories import make_intern


def test_score_leadership_components_sum_to_total(db_session):
    intern = make_intern(
        db_session,
        email="lead1@example.com",
        leadership_score=8.0,
        communication_score=7.0,
        attendance_pct=90.0,
        github_contributions=100,
    )
    result = leadership_service.score_leadership(intern, history=[])
    contributions = sum(c["contribution"] for c in result["components"].values())
    assert result["total_score"] == pytest.approx(round(contributions * 100, 2))
    assert 0.0 <= result["total_score"] <= 100.0


def test_score_leadership_weights_sum_to_one():
    assert sum(leadership_service.LEADERSHIP_WEIGHTS.values()) == pytest.approx(1.0)


def test_team_history_defaults_neutral_with_no_shared_history(db_session):
    intern = make_intern(db_session, email="lead2@example.com")
    result = leadership_service.score_leadership(intern, history=[])
    assert result["components"]["team_history"]["raw_score"] == 0.5


def test_team_history_reflects_past_outcome_ratings(db_session):
    intern = make_intern(db_session, email="lead3@example.com")
    history = [models.TeamHistory(intern_id=intern.id, past_team_name="Alpha", outcome_rating=9.0)]
    result = leadership_service.score_leadership(intern, history=history)
    assert result["components"]["team_history"]["raw_score"] == pytest.approx(0.9)


def test_higher_leadership_and_communication_scores_higher(db_session):
    strong = make_intern(
        db_session, email="strong@example.com", leadership_score=9.0, communication_score=9.0, attendance_pct=98.0
    )
    weak = make_intern(
        db_session, email="weak@example.com", leadership_score=2.0, communication_score=2.0, attendance_pct=60.0
    )
    strong_score = leadership_service.score_leadership(strong, history=[])["total_score"]
    weak_score = leadership_service.score_leadership(weak, history=[])["total_score"]
    assert strong_score > weak_score


def test_rank_leadership_orders_descending_and_breaks_ties_by_id(db_session):
    a = make_intern(db_session, email="a@example.com", leadership_score=5.0, communication_score=5.0)
    b = make_intern(db_session, email="b@example.com", leadership_score=5.0, communication_score=5.0)
    ranking = leadership_service.rank_leadership([b, a], history_by_intern={})
    assert [r["intern_id"] for r in ranking] == sorted([a.id, b.id])


def test_suggest_leader_picks_top_of_ranking(db_session):
    strong = make_intern(db_session, email="s2@example.com", leadership_score=9.0, communication_score=9.0)
    weak = make_intern(db_session, email="w2@example.com", leadership_score=1.0, communication_score=1.0)
    leader = leadership_service.suggest_leader([weak, strong], history_by_intern={})
    assert leader["intern_id"] == strong.id


def test_suggest_leader_raises_on_empty_team():
    with pytest.raises(ValueError):
        leadership_service.suggest_leader([], history_by_intern={})


def test_team_skill_breadth_counts_distinct_skills(db_session):
    intern = make_intern(db_session, email="breadth@example.com", technology_stack="React, Node.js, MongoDB")
    assert leadership_service.team_skill_breadth(intern) == 3
