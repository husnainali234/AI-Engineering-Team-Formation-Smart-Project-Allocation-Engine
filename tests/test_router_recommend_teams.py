def _make_interns(client, n, prefix="rec"):
    created = []
    for i in range(n):
        resp = client.post(
            "/interns",
            json={
                "full_name": f"{prefix}{i}",
                "email": f"{prefix}{i}@example.com",
                "technology_stack": "React, Node.js" if i % 2 == 0 else "Django, Postgres",
                "attendance_pct": 90.0,
                "leadership_score": 6.0,
                "communication_score": 6.0,
            },
        )
        created.append(resp.json())
    return created


def test_recommend_teams_409_when_not_enough_candidates(client):
    response = client.post("/recommend-teams", json={"intern_ids": []})
    # No intern_ids -> falls back to the (empty) available/unassigned/embedded pool
    assert response.status_code == 409


def test_recommend_teams_404_for_unknown_intern_ids(client):
    response = client.post("/recommend-teams", json={"intern_ids": [9999, 8888]})
    assert response.status_code == 404


def test_recommend_teams_returns_fully_wired_teams(client, fake_embedding_model):
    interns = _make_interns(client, 8)
    client.post(
        "/projects",
        json={"title": "React Dashboard", "required_tech_stack": "React, Node.js, Django, Postgres"},
    )

    response = client.post(
        "/recommend-teams",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 4, "algorithm": "kmeans"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["algorithm"] == "kmeans"
    total_members = sum(len(t["members"]) for t in body["teams"])
    assert total_members + len(body["unassigned_intern_ids"]) == 8
    assert len(body["teams"]) >= 1

    for team in body["teams"]:
        assert team["id"] is not None
        assert team["suggested_leader_intern_id"] in [m["intern_id"] for m in team["members"]]
        assert any(m["role"] == "Lead" for m in team["members"])
        assert team["skill_matrix"]
        assert 0.0 <= team["compatibility_score"] <= 100.0
        assert 0.0 <= team["success_probability"] <= 100.0
        assert 0.0 <= team["overall_score"] <= 100.0
        assert isinstance(team["risks"], list)

        # Day 11: Explainable AI Layer — every recommended team carries its
        # own SHAP-derived explanation, same shape as /success-probability.
        explanation = team["explanation"]
        assert len(explanation["factors"]) == 3
        assert explanation["reasons"]
        assert explanation["summary"]

    # Persistence check: the first recommended team should be readable via
    # the plain GET /teams/{id} the Day 1-3 CRUD router already exposes.
    team_id = body["teams"][0]["id"]
    team_out = client.get(f"/teams/{team_id}").json()
    assert len(team_out["members"]) >= 1
    assert team_out["compatibility_score"] == body["teams"][0]["compatibility_score"]


def test_recommend_teams_populates_workload_when_project_matched(client, fake_embedding_model):
    interns = _make_interns(client, 4, prefix="wl")
    client.post(
        "/projects",
        json={"title": "Full Stack App", "required_tech_stack": "React, Node.js, Django, Postgres"},
    )

    response = client.post(
        "/recommend-teams",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 4, "algorithm": "kmeans"},
    )
    assert response.status_code == 200
    body = response.json()

    team = body["teams"][0]
    if team["project"] is not None:
        assert team["workload"]
        assigned_ids = {row["intern_id"] for row in team["workload"]}
        assert assigned_ids.issubset({m["intern_id"] for m in team["members"]})


def test_recommend_teams_defaults_to_available_unassigned_pool(client, fake_embedding_model):
    interns = _make_interns(client, 4, prefix="pool2")
    # First call consumes these interns into a team.
    client.post(
        "/recommend-teams",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 4},
    )
    # A second call with no intern_ids should find nobody left unassigned.
    response = client.post("/recommend-teams", json={})
    assert response.status_code == 409
