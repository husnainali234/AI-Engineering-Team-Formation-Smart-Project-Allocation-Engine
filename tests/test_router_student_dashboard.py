from tests.factories import make_intern, make_project, make_team


def test_student_dashboard_404_for_unknown_intern(client):
    assert client.get("/student/9999/dashboard").status_code == 404


def test_student_dashboard_no_team_yet(client):
    intern = client.post(
        "/interns",
        json={"full_name": "Solo Student", "email": "sdr1@example.com", "technology_stack": "React"},
    ).json()

    response = client.get(f"/student/{intern['id']}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["intern_id"] == intern["id"]
    assert body["team"] is None


def test_student_dashboard_reflects_assigned_team(client, db_session):
    intern = client.post(
        "/interns",
        json={
            "full_name": "Assigned Student",
            "email": "sdr2@example.com",
            "technology_stack": "Django",
            "leadership_score": 9.0,
        },
    ).json()
    teammate = client.post(
        "/interns",
        json={"full_name": "Teammate", "email": "sdr3@example.com", "technology_stack": "React"},
    ).json()
    project = make_project(db_session, "Student Router Project")
    team = make_team(
        db_session, "Student Router Team",
        member_ids=[intern["id"], teammate["id"]],
        compatibility_score=72.0,
    )
    team.project_id = project.id
    db_session.add(team)
    db_session.commit()

    response = client.get(f"/student/{intern['id']}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["team"]["team_id"] == team.id
    assert body["team"]["project_title"] == "Student Router Project"
    assert body["team"]["compatibility_score"] == 72.0
    assert body["team"]["teammates"] == ["Teammate"]
    assert any("leadership" in s.lower() for s in body["strengths"])


def test_student_dashboard_shows_applied_workload_responsibility(client, db_session):
    intern = client.post(
        "/interns",
        json={"full_name": "Worker Student", "email": "sdr4@example.com", "technology_stack": "React"},
    ).json()
    project = make_project(db_session, "Workload Project", required_tech_stack="React")
    team = make_team(db_session, "Workload Team", member_ids=[intern["id"]])
    team.project_id = project.id
    db_session.add(team)
    db_session.commit()

    apply_response = client.post(f"/workload/team/{team.id}/apply")
    assert apply_response.status_code == 200

    response = client.get(f"/student/{intern['id']}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["team"]["suggested_responsibility"] is not None
