from app.services import admin_analytics_service
from tests.factories import make_intern, make_project, make_team


def test_cross_team_analytics_averages_only_scored_teams(db_session):
    a = make_intern(db_session, email="ata1@example.com")
    b = make_intern(db_session, email="ata2@example.com")
    scored = make_team(db_session, "Scored Team", member_ids=[a.id, b.id], compatibility_score=80.0)
    scored.success_probability = 0.70  # persisted 0-1 (see app/models.py); service rescales to 0-100
    db_session.add(scored)
    db_session.commit()

    unscored = make_team(db_session, "Unscored Team", member_ids=[a.id])

    result = admin_analytics_service.cross_team_analytics([scored, unscored])

    assert result["team_count"] == 2
    # Only the scored team's 80.0/70.0 should feed the averages — the
    # unscored team's default 0.0s must not drag them down.
    assert result["avg_compatibility_score"] == 80.0
    assert result["avg_success_probability"] == 70.0
    assert result["size_distribution"] == {"2": 1, "1": 1}


def test_cross_team_analytics_counts_project_and_risk_status(db_session):
    project = make_project(db_session, "Demo Project")
    intern = make_intern(db_session, email="ata3@example.com")
    with_project = make_team(db_session, "With Project", member_ids=[intern.id])
    with_project.project_id = project.id
    with_project.risk_notes = "No risks identified."
    db_session.add(with_project)

    flagged = make_team(db_session, "Flagged Team", member_ids=[intern.id])
    flagged.risk_notes = "[HIGH] low_attendance: Someone is absent a lot."
    db_session.add(flagged)

    unassessed = make_team(db_session, "Unassessed Team", member_ids=[intern.id])
    db_session.commit()

    result = admin_analytics_service.cross_team_analytics([with_project, flagged, unassessed])

    assert result["teams_with_project"] == 1
    assert result["teams_without_project"] == 2
    assert result["teams_assessed_for_risk"] == 2
    assert result["teams_flagged_at_risk"] == 1


def test_project_success_rates_counts_teams_without_matches(db_session):
    matched = make_project(db_session, "Matched Project")
    unmatched = make_project(db_session, "Unmatched Project")
    intern = make_intern(db_session, email="ata4@example.com")
    team = make_team(db_session, "Team A", member_ids=[intern.id], compatibility_score=60.0)
    team.project_id = matched.id
    team.success_probability = 0.55  # persisted 0-1 (see app/models.py); service rescales to 0-100
    db_session.add(team)
    db_session.commit()
    db_session.refresh(matched)
    db_session.refresh(unmatched)

    result = admin_analytics_service.project_success_rates([matched, unmatched])

    assert result["project_count"] == 2
    assert result["projects_without_teams"] == 1
    matched_row = next(r for r in result["projects"] if r["project_id"] == matched.id)
    assert matched_row["team_count"] == 1
    assert matched_row["avg_success_probability"] == 55.0
    unmatched_row = next(r for r in result["projects"] if r["project_id"] == unmatched.id)
    assert unmatched_row["team_count"] == 0
    assert unmatched_row["avg_success_probability"] is None


def test_resource_utilization_splits_assigned_and_available(db_session):
    assigned = make_intern(db_session, email="ata5@example.com", is_available=True)
    available_unassigned = make_intern(db_session, email="ata6@example.com", is_available=True)
    unavailable_unassigned = make_intern(db_session, email="ata7@example.com", is_available=False)
    make_team(db_session, "Util Team", member_ids=[assigned.id])

    result = admin_analytics_service.resource_utilization(
        [assigned, available_unassigned, unavailable_unassigned],
        assigned_intern_ids={assigned.id},
    )

    assert result["total_interns"] == 3
    assert result["assigned_count"] == 1
    assert result["unassigned_count"] == 2
    assert result["available_and_unassigned_count"] == 1
    assert result["assigned_pct"] == round(100 / 3, 2)


def test_resource_utilization_handles_no_interns():
    result = admin_analytics_service.resource_utilization([], set())
    assert result["total_interns"] == 0
    assert result["assigned_pct"] == 0.0
    assert result["avg_attendance_pct"] == 0.0
