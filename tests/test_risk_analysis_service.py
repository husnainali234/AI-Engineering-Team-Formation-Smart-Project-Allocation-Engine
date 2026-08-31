from app.services import risk_analysis_service
from tests.factories import make_intern


def test_assess_risks_flags_skill_overlap_for_identical_skills(db_session):
    a = make_intern(db_session, email="ra1@example.com", technology_stack="React", leadership_score=8.0, attendance_pct=95.0)
    b = make_intern(db_session, email="ra2@example.com", technology_stack="React", leadership_score=8.0, attendance_pct=95.0)
    risks = risk_analysis_service.assess_risks([a, b], compatibility_score=90.0)
    types = {r["type"] for r in risks}
    assert "skill_overlap" in types


def test_assess_risks_flags_low_attendance(db_session):
    a = make_intern(db_session, full_name="Low Attendance Intern", email="ra3@example.com", technology_stack="React", leadership_score=8.0, attendance_pct=40.0)
    b = make_intern(db_session, email="ra4@example.com", technology_stack="Django", leadership_score=8.0, attendance_pct=95.0)
    risks = risk_analysis_service.assess_risks([a, b], compatibility_score=90.0)
    low_attendance = next(r for r in risks if r["type"] == "low_attendance")
    assert low_attendance["severity"] == "high"
    assert "Low Attendance Intern" in low_attendance["message"]


def test_assess_risks_flags_leadership_gap(db_session):
    a = make_intern(db_session, email="ra5@example.com", technology_stack="React", leadership_score=2.0, attendance_pct=95.0)
    b = make_intern(db_session, email="ra6@example.com", technology_stack="Django", leadership_score=3.0, attendance_pct=95.0)
    risks = risk_analysis_service.assess_risks([a, b], compatibility_score=90.0)
    types = {r["type"] for r in risks}
    assert "leadership_gap" in types


def test_assess_risks_flags_high_conflict_likelihood(db_session):
    a = make_intern(db_session, email="ra7@example.com", technology_stack="React", leadership_score=8.0, attendance_pct=95.0)
    b = make_intern(db_session, email="ra8@example.com", technology_stack="Django", leadership_score=8.0, attendance_pct=95.0)
    risks = risk_analysis_service.assess_risks([a, b], compatibility_score=20.0)
    conflict = next(r for r in risks if r["type"] == "high_conflict_likelihood")
    assert conflict["severity"] == "high"


def test_assess_risks_skips_conflict_check_when_compatibility_score_is_none(db_session):
    a = make_intern(db_session, email="ra9@example.com", technology_stack="React", leadership_score=8.0, attendance_pct=95.0)
    b = make_intern(db_session, email="ra10@example.com", technology_stack="Django", leadership_score=8.0, attendance_pct=95.0)
    risks = risk_analysis_service.assess_risks([a, b], compatibility_score=None)
    types = {r["type"] for r in risks}
    assert "high_conflict_likelihood" not in types


def test_assess_risks_returns_empty_for_healthy_team(db_session):
    a = make_intern(db_session, email="ra11@example.com", technology_stack="React, Node.js", leadership_score=8.0, attendance_pct=95.0)
    b = make_intern(db_session, email="ra12@example.com", technology_stack="Django, Postgres", leadership_score=7.0, attendance_pct=92.0)
    risks = risk_analysis_service.assess_risks([a, b], compatibility_score=85.0)
    assert risks == []
