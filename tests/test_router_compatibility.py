def test_pairwise_compatibility_requires_two_different_interns(client):
    intern = client.post("/interns", json={"full_name": "A", "email": "a7@example.com"}).json()
    response = client.get(f"/compatibility/pair?intern_a_id={intern['id']}&intern_b_id={intern['id']}")
    assert response.status_code == 422


def test_pairwise_compatibility_404_for_unknown_intern(client):
    intern = client.post("/interns", json={"full_name": "A", "email": "a8@example.com"}).json()
    response = client.get(f"/compatibility/pair?intern_a_id={intern['id']}&intern_b_id=9999")
    assert response.status_code == 404


def test_pairwise_compatibility_returns_breakdown(client):
    a = client.post("/interns", json={"full_name": "A", "email": "a9@example.com"}).json()
    b = client.post("/interns", json={"full_name": "B", "email": "b9@example.com"}).json()

    response = client.get(f"/compatibility/pair?intern_a_id={a['id']}&intern_b_id={b['id']}")

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["total_score"] <= 100
    assert set(body["components"].keys()) == {
        "communication", "leadership", "attendance", "team_history", "skill_diversity", "github_activity",
    }


def test_team_compatibility_404_for_unknown_team(client):
    assert client.get("/compatibility/team/9999").status_code == 404


def test_team_compatibility_and_recalculate_persist_score(client, db_session):
    from tests.factories import make_team

    a = client.post("/interns", json={"full_name": "A", "email": "a10@example.com"}).json()
    b = client.post("/interns", json={"full_name": "B", "email": "b10@example.com"}).json()
    team = make_team(db_session, "Gamma", member_ids=[a["id"], b["id"]])

    preview = client.get(f"/compatibility/team/{team.id}")
    assert preview.status_code == 200
    assert preview.json()["member_count"] == 2

    recalculated = client.post(f"/compatibility/team/{team.id}/recalculate")
    assert recalculated.status_code == 200

    team_resp = client.get(f"/teams/{team.id}")
    assert team_resp.json()["compatibility_score"] == recalculated.json()["average_score"]
