def test_team_skill_matrix_404_for_unknown_team(client):
    assert client.get("/skill-matrix/team/9999").status_code == 404


def test_team_skill_matrix_returns_expected_shape(client, fake_embedding_model, db_session):
    from tests.factories import assign_skill, make_skill, make_team

    intern_a = client.post("/interns", json={"full_name": "A", "email": "a3@example.com"}).json()
    intern_b = client.post("/interns", json={"full_name": "B", "email": "b3@example.com"}).json()

    react = make_skill(db_session, "React")
    from app import models
    assign_skill(db_session, db_session.get(models.Intern, intern_a["id"]), react, proficiency=4)
    assign_skill(db_session, db_session.get(models.Intern, intern_b["id"]), react, proficiency=2)

    team = make_team(db_session, "Alpha", member_ids=[intern_a["id"], intern_b["id"]])

    response = client.get(f"/skill-matrix/team/{team.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["member_count"] == 2
    react_row = next(row for row in body["skills"] if row["skill_name"] == "React")
    assert react_row["intern_count"] == 2
    assert react_row["avg_proficiency"] == 3.0


def test_technology_frequency_global_scope(client, fake_embedding_model):
    client.post("/interns", json={"full_name": "A", "email": "a4@example.com", "technology_stack": "React"})
    client.post("/interns", json={"full_name": "B", "email": "b4@example.com", "technology_stack": "React"})

    response = client.get("/skill-matrix/technology-frequency")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "global"
    assert body["frequency"]["React"] == 2


def test_proficiency_aggregation_team_scope_404_for_missing_team(client):
    assert client.get("/skill-matrix/proficiency-aggregation?team_id=999").status_code == 404
