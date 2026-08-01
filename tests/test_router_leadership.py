from tests.factories import make_team


def test_intern_leadership_score_404_for_unknown_intern(client):
    assert client.get("/leadership/interns/9999/score").status_code == 404


def test_intern_leadership_score_returns_breakdown(client):
    intern = client.post(
        "/interns",
        json={"full_name": "Lead Candidate", "email": "lc1@example.com", "leadership_score": 8.0, "communication_score": 7.0},
    ).json()
    response = client.get(f"/leadership/interns/{intern['id']}/score")
    assert response.status_code == 200
    body = response.json()
    assert body["intern_id"] == intern["id"]
    assert "leadership_score" in body["components"]


def test_suggest_team_leader_404_for_unknown_team(client):
    assert client.get("/leadership/team/9999/suggest").status_code == 404


def test_suggest_team_leader_409_for_empty_team(client, db_session):
    team = make_team(db_session, "Empty")
    assert client.get(f"/leadership/team/{team.id}/suggest").status_code == 409


def test_suggest_team_leader_returns_ranking(client, db_session):
    strong = client.post(
        "/interns", json={"full_name": "Strong", "email": "strong7@example.com", "leadership_score": 9.0, "communication_score": 9.0}
    ).json()
    weak = client.post(
        "/interns", json={"full_name": "Weak", "email": "weak7@example.com", "leadership_score": 1.0, "communication_score": 1.0}
    ).json()
    team = make_team(db_session, "Squad", member_ids=[strong["id"], weak["id"]])
    response = client.get(f"/leadership/team/{team.id}/suggest")
    assert response.status_code == 200
    body = response.json()
    assert body["suggested_leader_intern_id"] == strong["id"]
    assert len(body["ranking"]) == 2


def test_apply_team_leader_persists_role(client, db_session):
    strong = client.post(
        "/interns", json={"full_name": "Strong2", "email": "strong8@example.com", "leadership_score": 9.0, "communication_score": 9.0}
    ).json()
    weak = client.post(
        "/interns", json={"full_name": "Weak2", "email": "weak8@example.com", "leadership_score": 1.0, "communication_score": 1.0}
    ).json()
    team = make_team(db_session, "Squad2", member_ids=[strong["id"], weak["id"]])
    response = client.post(f"/leadership/team/{team.id}/apply")
    assert response.status_code == 200
    team_out = client.get(f"/teams/{team.id}").json()
    roles = {m["intern_id"]: m["role"] for m in team_out["members"]}
    assert roles[strong["id"]] == "Lead"
    assert roles[weak["id"]] == "Member"
