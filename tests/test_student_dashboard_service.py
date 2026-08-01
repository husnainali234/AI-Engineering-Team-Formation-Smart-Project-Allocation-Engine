from app.services import student_dashboard_service
from tests.factories import assign_skill, make_intern, make_project, make_skill, make_team


def test_identify_strengths_flags_signals_above_threshold(db_session):
    intern = make_intern(
        db_session,
        email="sds1@example.com",
        leadership_score=8.0,
        communication_score=8.5,
        case_study_performance=90.0,
        attendance_pct=98.0,
        github_contributions=40,
    )
    strengths = student_dashboard_service.identify_strengths(intern)
    assert any("leadership" in s.lower() for s in strengths)
    assert any("communicator" in s.lower() for s in strengths)
    assert any("case-study" in s.lower() for s in strengths)
    assert any("attendance" in s.lower() for s in strengths)
    assert any("github" in s.lower() for s in strengths)


def test_identify_strengths_empty_when_nothing_clears_threshold(db_session):
    intern = make_intern(
        db_session,
        email="sds2@example.com",
        leadership_score=2.0,
        communication_score=2.0,
        case_study_performance=40.0,
        attendance_pct=60.0,
        github_contributions=1,
    )
    assert student_dashboard_service.identify_strengths(intern) == []


def test_top_skills_ranks_by_proficiency_and_excludes_low_ones(db_session):
    intern = make_intern(db_session, email="sds3@example.com")
    strong = make_skill(db_session, "Kubernetes")
    weak = make_skill(db_session, "Bash")
    assign_skill(db_session, intern, strong, proficiency=5)
    assign_skill(db_session, intern, weak, proficiency=2)

    skills = student_dashboard_service.top_skills(intern)
    names = [s["skill_name"] for s in skills]
    assert names == ["Kubernetes"]


def test_top_skills_ignores_technology_stack_only_entries(db_session):
    intern = make_intern(db_session, email="sds4@example.com", technology_stack="React, Node.js")
    assert student_dashboard_service.top_skills(intern) == []


def test_build_team_view_excludes_self_from_teammates(db_session):
    a = make_intern(db_session, full_name="Alpha", email="sds5@example.com")
    b = make_intern(db_session, full_name="Bravo", email="sds6@example.com")
    project = make_project(db_session, "Team View Project")
    team = make_team(db_session, "Team View Team", member_ids=[a.id, b.id], compatibility_score=88.0)
    team.project_id = project.id
    team.success_probability = 0.60  # persisted 0-1 (see app/models.py); service rescales to 0-100
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)

    a_member = next(m for m in team.members if m.intern_id == a.id)
    view = student_dashboard_service.build_team_view(a_member)

    assert view["team_id"] == team.id
    assert view["teammates"] == ["Bravo"]
    assert view["compatibility_score"] == 88.0
    assert view["success_probability"] == 60.0
    assert view["project_title"] == "Team View Project"
    assert view["suggested_responsibility"] is None
