from tests.factories import make_team


def test_cross_team_analytics_empty_state(client):
    response = client.get("/admin-analytics/teams")
    assert response.status_code == 200
    body = response.json()
    assert body["team_count"] == 0
    assert body["teams"] == []
    assert body["avg_compatibility_score"] is None


def test_cross_team_analytics_reflects_created_teams(client, db_session):
    intern = client.post(
        "/interns",
        json={"full_name": "Cross Team Intern", "email": "cta1@example.com", "technology_stack": "React"},
    ).json()
    team = make_team(db_session, "Analytics Team", member_ids=[intern["id"]], compatibility_score=75.0)

    response = client.get("/admin-analytics/teams")
    assert response.status_code == 200
    body = response.json()
    assert body["team_count"] == 1
    assert body["teams"][0]["team_id"] == team.id
    assert body["teams"][0]["member_count"] == 1
    assert body["avg_compatibility_score"] == 75.0


def test_project_success_rates_lists_projects_without_teams(client):
    client.post(
        "/projects",
        json={"title": "Lonely Project", "required_tech_stack": "React", "difficulty_level": "Medium"},
    )

    response = client.get("/admin-analytics/projects")
    assert response.status_code == 200
    body = response.json()
    assert body["project_count"] == 1
    assert body["projects_without_teams"] == 1
    assert body["projects"][0]["team_count"] == 0


def test_resource_utilization_reflects_intern_pool(client, db_session):
    client.post(
        "/interns",
        json={"full_name": "Util Intern", "email": "ru1@example.com", "technology_stack": "Django", "is_available": True},
    )
    unassigned_response = client.post(
        "/interns",
        json={"full_name": "Unassigned Intern", "email": "ru2@example.com", "technology_stack": "React", "is_available": True},
    ).json()
    make_team(db_session, "Util Router Team", member_ids=[])  # doesn't affect assignment counts

    response = client.get("/admin-analytics/resource-utilization")
    assert response.status_code == 200
    body = response.json()
    assert body["total_interns"] == 2
    assert body["unassigned_count"] == 2
    assert body["available_and_unassigned_count"] == 2
