from app.services import success_probability_service
from tests.factories import make_intern


def test_compute_success_probability_returns_bounded_result(db_session):
    a = make_intern(db_session, email="sp1@example.com", technology_stack="React", attendance_pct=90.0)
    b = make_intern(db_session, email="sp2@example.com", technology_stack="Django", attendance_pct=85.0)
    result = success_probability_service.compute_success_probability([a, b], feedback_by_intern={})
    assert 0.0 <= result["success_probability"] <= 100.0
    assert set(result["features"].keys()) == {"team_balance", "avg_attendance_pct", "avg_feedback_score"}


def test_compute_success_probability_empty_team_returns_zero():
    result = success_probability_service.compute_success_probability([], feedback_by_intern={})
    assert result["success_probability"] == 0.0


def test_compute_success_probability_uses_neutral_feedback_when_none_on_record(db_session):
    a = make_intern(db_session, email="sp3@example.com")
    result = success_probability_service.compute_success_probability([a], feedback_by_intern={})
    assert result["features"]["avg_feedback_score"] == success_probability_service.NEUTRAL_FEEDBACK_SCORE


def test_compute_success_probability_averages_feedback_scores(db_session):
    a = make_intern(db_session, email="sp4@example.com")

    class _Feedback:
        def __init__(self, score):
            self.score = score

    feedback_by_intern = {a.id: [_Feedback(8.0), _Feedback(6.0)]}
    result = success_probability_service.compute_success_probability([a], feedback_by_intern)
    assert result["features"]["avg_feedback_score"] == 7.0


def test_compute_success_probability_higher_for_stronger_signals(db_session):
    class _Feedback:
        def __init__(self, score):
            self.score = score

    strong_a = make_intern(db_session, email="sp5@example.com", technology_stack="React", attendance_pct=99.0)
    strong_b = make_intern(db_session, email="sp6@example.com", technology_stack="Django, Docker, AWS", attendance_pct=98.0)
    strong_feedback = {strong_a.id: [_Feedback(9.5)], strong_b.id: [_Feedback(9.5)]}
    strong_result = success_probability_service.compute_success_probability([strong_a, strong_b], strong_feedback)

    weak_a = make_intern(db_session, email="sp7@example.com", technology_stack="React", attendance_pct=45.0)
    weak_b = make_intern(db_session, email="sp8@example.com", technology_stack="React", attendance_pct=40.0)
    weak_feedback = {weak_a.id: [_Feedback(1.0)], weak_b.id: [_Feedback(1.0)]}
    weak_result = success_probability_service.compute_success_probability([weak_a, weak_b], weak_feedback)

    assert strong_result["success_probability"] > weak_result["success_probability"]
