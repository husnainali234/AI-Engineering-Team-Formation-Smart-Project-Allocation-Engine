from tests.factories import make_team


def test_recommend_projects_404_for_unknown_team(client):
    assert client.get("/project-matching/team/9999").status_code == 404


def test_recommend_projects_409_when_team_has_no_members(client, db_session):
    team = make_team(db_session, "Empty Project Team")
    assert client.get(f"/project-matching/team/{team.id}").status_code == 409


def test_recommend_projects_409_when_no_projects_exist(client, db_session):
    intern = client.post("/interns", json={"full_name": "A", "email": "pm1@example.com"}).json()
    team = make_team(db_session, "No Projects Team", member_ids=[intern["id"]])
    assert client.get(f"/project-matching/team/{team.id}").status_code == 409


def test_recommend_projects_returns_ranked_list(client, db_session):
    intern = client.post(
        "/interns", json={"full_name": "Laravel Dev", "email": "pm2@example.com", "technology_stack": "Laravel, MySQL"}
    ).json()
    client.post("/projects", json={"title": "Laravel Shop", "required_tech_stack": "Laravel, MySQL"})
    client.post("/projects", json={"title": "ML Pipeline", "required_tech_stack": "Python, TensorFlow"})
    team = make_team(db_session, "Laravel Team", member_ids=[intern["id"]])

    response = client.get(f"/project-matching/team/{team.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"][0]["title"] == "Laravel Shop"


def test_assign_project_persists_to_team(client, db_session):
    intern = client.post(
        "/interns", json={"full_name": "Vue Dev", "email": "pm3@example.com", "technology_stack": "Vue"}
    ).json()
    project = client.post("/projects", json={"title": "Vue Dashboard", "required_tech_stack": "Vue"}).json()
    team = make_team(db_session, "Vue Team", member_ids=[intern["id"]])

    response = client.post(f"/project-matching/team/{team.id}/assign?project_id={project['id']}")
    assert response.status_code == 200
    assert response.json()["project_id"] == project["id"]

    team_out = client.get(f"/teams/{team.id}").json()
    assert team_out["project_id"] == project["id"]


def test_assign_project_auto_picks_top_recommendation(client, db_session):
    intern = client.post(
        "/interns", json={"full_name": "React Dev", "email": "pm4@example.com", "technology_stack": "React"}
    ).json()
    client.post("/projects", json={"title": "Unrelated", "required_tech_stack": "Rust"})
    react_project = client.post("/projects", json={"title": "React App", "required_tech_stack": "React"}).json()
    team = make_team(db_session, "Auto Team", member_ids=[intern["id"]])

    response = client.post(f"/project-matching/team/{team.id}/assign")
    assert response.status_code == 200
    assert response.json()["project_id"] == react_project["id"]


def test_workload_409_when_no_project_assigned(client, db_session):
    intern = client.post("/interns", json={"full_name": "W", "email": "wl1@example.com"}).json()
    team = make_team(db_session, "No Project Team", member_ids=[intern["id"]])
    assert client.get(f"/workload/team/{team.id}").status_code == 409


def test_workload_apply_persists_responsibility(client, db_session):
    intern = client.post(
        "/interns", json={"full_name": "Node Dev", "email": "wl2@example.com", "technology_stack": "Node.js"}
    ).json()
    project = client.post("/projects", json={"title": "Node API", "required_tech_stack": "Node.js"}).json()
    team = make_team(db_session, "Node Team", member_ids=[intern["id"]])
    client.post(f"/project-matching/team/{team.id}/assign?project_id={project['id']}")

    preview = client.get(f"/workload/team/{team.id}")
    assert preview.status_code == 200
    assert preview.json()["assignments"][0]["assigned_skills"] == ["Node.js"]

    applied = client.post(f"/workload/team/{team.id}/apply")
    assert applied.status_code == 200

    team_out = client.get(f"/teams/{team.id}").json()
    member = next(m for m in team_out["members"] if m["intern_id"] == intern["id"])
    assert "Node.js" in member["suggested_responsibility"]
