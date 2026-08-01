from app.services import team_chemistry_service
from tests.factories import make_feedback, make_intern


def test_predict_team_chemistry_empty_team_returns_zero():
    result = team_chemistry_service.predict_team_chemistry([], [])
    assert result["chemistry_score"] == 0.0
    assert result["label"] == "Fragile"


def test_one_strong_leader_scores_higher_than_two_competing_leaders(db_session):
    strong_leader = make_intern(db_session, email="tcs1@example.com", leadership_score=8.0)
    member = make_intern(db_session, email="tcs2@example.com", leadership_score=3.0)
    one_leader_result = team_chemistry_service.predict_team_chemistry([strong_leader, member], [])

    co_leader = make_intern(db_session, email="tcs3@example.com", leadership_score=8.0)
    two_leader_result = team_chemistry_service.predict_team_chemistry([strong_leader, co_leader], [])

    assert one_leader_result["components"]["leadership_balance"]["raw_score"] == 1.0
    assert two_leader_result["components"]["leadership_balance"]["raw_score"] < 1.0
    assert one_leader_result["chemistry_score"] > two_leader_result["chemistry_score"]
    assert any("strong leaders" in f for f in two_leader_result["flags"])


def test_zero_strong_leaders_flags_no_clear_leader(db_session):
    a = make_intern(db_session, email="tcs4@example.com", leadership_score=2.0)
    b = make_intern(db_session, email="tcs5@example.com", leadership_score=3.0)
    result = team_chemistry_service.predict_team_chemistry([a, b], [])
    assert result["components"]["leadership_balance"]["raw_score"] == 0.4
    assert any("No clear strong leader" in f for f in result["flags"])


def test_shared_interests_scores_higher_when_members_overlap(db_session):
    a = make_intern(db_session, email="tcs6@example.com", project_interests="AI/ML, Fintech")
    b_shared = make_intern(db_session, email="tcs7@example.com", project_interests="AI/ML, Healthcare")
    b_disjoint = make_intern(db_session, email="tcs8@example.com", project_interests="Gaming, Robotics")

    shared_result = team_chemistry_service.predict_team_chemistry([a, b_shared], [])
    disjoint_result = team_chemistry_service.predict_team_chemistry([a, b_disjoint], [])

    assert shared_result["components"]["shared_interests"]["raw_score"] > 0.0
    assert disjoint_result["components"]["shared_interests"]["raw_score"] == 0.0
    assert any("interests" in f for f in disjoint_result["flags"])


def test_shared_interests_neutral_when_fewer_than_two_have_interests_on_record(db_session):
    a = make_intern(db_session, email="tcs9@example.com", project_interests=None)
    b = make_intern(db_session, email="tcs10@example.com", project_interests=None)
    result = team_chemistry_service.predict_team_chemistry([a, b], [])
    assert result["components"]["shared_interests"]["raw_score"] == 0.5
    assert not any("interests" in f for f in result["flags"])


def test_communication_spread_penalizes_uneven_communicators(db_session):
    even_a = make_intern(db_session, email="tcs11@example.com", communication_score=6.0)
    even_b = make_intern(db_session, email="tcs12@example.com", communication_score=6.5)
    even_result = team_chemistry_service.predict_team_chemistry([even_a, even_b], [])

    uneven_a = make_intern(db_session, email="tcs13@example.com", communication_score=9.5)
    uneven_b = make_intern(db_session, email="tcs14@example.com", communication_score=1.0)
    uneven_result = team_chemistry_service.predict_team_chemistry([uneven_a, uneven_b], [])

    assert even_result["components"]["communication_spread"]["raw_score"] > uneven_result["components"]["communication_spread"]["raw_score"]


def test_feedback_sentiment_neutral_without_comments(db_session):
    intern = make_intern(db_session, email="tcs15@example.com")
    make_feedback(db_session, intern, comments=None)
    result = team_chemistry_service.predict_team_chemistry([intern], intern.feedback_entries)
    assert result["components"]["feedback_sentiment"]["raw_score"] == 0.5


def test_feedback_sentiment_flags_negative_keywords(db_session):
    intern = make_intern(db_session, email="tcs16@example.com")
    make_feedback(db_session, intern, comments="Repeated conflict and tension with teammates this sprint.")
    result = team_chemistry_service.predict_team_chemistry([intern], intern.feedback_entries)
    assert result["components"]["feedback_sentiment"]["raw_score"] < 0.5
    assert any("friction" in f for f in result["flags"])


def test_feedback_sentiment_rewards_positive_keywords(db_session):
    intern = make_intern(db_session, email="tcs17@example.com")
    make_feedback(db_session, intern, comments="Great teamwork and a real team player this cycle.")
    result = team_chemistry_service.predict_team_chemistry([intern], intern.feedback_entries)
    assert result["components"]["feedback_sentiment"]["raw_score"] > 0.5


def test_chemistry_weights_sum_to_one():
    assert round(sum(team_chemistry_service.CHEMISTRY_WEIGHTS.values()), 6) == 1.0


def test_label_thresholds():
    assert team_chemistry_service._label(80.0) == "Strong"
    assert team_chemistry_service._label(60.0) == "Workable"
    assert team_chemistry_service._label(20.0) == "Fragile"
