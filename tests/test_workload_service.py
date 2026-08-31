from app import models
from app.services import workload_service
from tests.factories import make_intern, make_project, make_skill, assign_skill


def _team_member(db, intern, team_id, role="Member"):
    member = models.TeamMember(team_id=team_id, intern_id=intern.id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def test_distribute_workload_matches_required_skill_to_proficient_member(db_session):
    react = make_skill(db_session, "React")
    strong = make_intern(db_session, email="w1@example.com", technology_stack="React")
    assign_skill(db_session, strong, react, proficiency=5)
    weak = make_intern(db_session, email="w2@example.com", technology_stack="React")
    assign_skill(db_session, weak, react, proficiency=2)
    team = models.Team(name="Workload Team")
    db_session.add(team)
    db_session.flush()
    members = [_team_member(db_session, strong, team.id), _team_member(db_session, weak, team.id)]
    project = make_project(db_session, title="React App", required_tech_stack="React")
    result = workload_service.distribute_workload(members, project)
    strong_row = next(r for r in result if r["intern_id"] == strong.id)
    assert "React" in strong_row["assigned_skills"]


def test_distribute_workload_gives_lead_fallback_when_no_skill_match(db_session):
    lead = make_intern(db_session, email="w3@example.com", technology_stack="React")
    team = models.Team(name="Fallback Team")
    db_session.add(team)
    db_session.flush()
    members = [_team_member(db_session, lead, team.id, role="Lead")]
    project = make_project(db_session, title="Unrelated Project", required_tech_stack="")
    result = workload_service.distribute_workload(members, project)
    assert result[0]["suggested_responsibility"] == workload_service.LEAD_FALLBACK_RESPONSIBILITY


def test_distribute_workload_assigns_unmatched_skill_to_generalist(db_session):
    generalist = make_intern(db_session, email="w4@example.com", technology_stack="React, Node.js, Docker")
    specialist = make_intern(db_session, email="w5@example.com", technology_stack="React")
    team = models.Team(name="Generalist Team")
    db_session.add(team)
    db_session.flush()
    members = [_team_member(db_session, generalist, team.id), _team_member(db_session, specialist, team.id)]
    project = make_project(db_session, title="Rust Service", required_tech_stack="Rust")
    result = workload_service.distribute_workload(members, project)
    generalist_row = next(r for r in result if r["intern_id"] == generalist.id)
    assert "Rust" in generalist_row["assigned_skills"]


def test_distribute_workload_orders_lead_first(db_session):
    member = make_intern(db_session, email="w6@example.com")
    lead = make_intern(db_session, email="w7@example.com")
    team = models.Team(name="Order Team")
    db_session.add(team)
    db_session.flush()
    members = [
        _team_member(db_session, member, team.id, role="Member"),
        _team_member(db_session, lead, team.id, role="Lead"),
    ]
    project = make_project(db_session, title="Generic Project", required_tech_stack="")
    result = workload_service.distribute_workload(members, project)
    assert result[0]["role"] == "Lead"


def test_required_skill_count_helper(db_session):
    project = make_project(db_session, title="Count Project", required_tech_stack="React, Node.js, MongoDB")
    assert workload_service.required_skill_count(project) == 3
