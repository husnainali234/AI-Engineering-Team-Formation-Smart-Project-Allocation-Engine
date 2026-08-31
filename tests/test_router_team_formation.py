def _make_interns(client, n, prefix="tf"):
    created = []
    for i in range(n):
        resp = client.post(
            "/interns",
            json={
                "full_name": f"{prefix}{i}",
                "email": f"{prefix}{i}@example.com",
                "technology_stack": "React, Node.js" if i % 2 == 0 else "Django, Postgres",
            },
        )
        created.append(resp.json())
    return created


def test_preview_409_when_not_enough_candidates(client):
    response = client.post("/team-formation/preview", json={"intern_ids": []})
    # No intern_ids -> falls back to the (empty) available/unassigned/embedded pool
    assert response.status_code == 409


def test_preview_404_for_unknown_intern_ids(client):
    response = client.post("/team-formation/preview", json={"intern_ids": [9999, 8888]})
    assert response.status_code == 404


def test_preview_returns_candidate_teams(client, fake_embedding_model):
    interns = _make_interns(client, 8)
    response = client.post(
        "/team-formation/preview",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 4, "algorithm": "kmeans"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm"] == "kmeans"
    total_members = sum(len(t["members"]) for t in body["teams"])
    assert total_members + len(body["unassigned_intern_ids"]) == 8
    for team in body["teams"]:
        assert team["suggested_leader_intern_id"] in [m["intern_id"] for m in team["members"]]
        assert any(m["role"] == "Lead" for m in team["members"])


def test_preview_rejects_unknown_algorithm(client, fake_embedding_model):
    interns = _make_interns(client, 4, prefix="alg")
    response = client.post(
        "/team-formation/preview",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 2, "algorithm": "graphdb"},
    )
    assert response.status_code == 422


def test_commit_persists_teams(client, fake_embedding_model):
    interns = _make_interns(client, 4, prefix="commit")
    response = client.post(
        "/team-formation/commit",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 4, "algorithm": "kmeans"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["teams"]) >= 1
    team_id = body["teams"][0]["id"]
    team_out = client.get(f"/teams/{team_id}").json()
    assert len(team_out["members"]) >= 1
    assert any(m["role"] == "Lead" for m in team_out["members"])


def test_commit_defaults_to_available_unassigned_pool(client, fake_embedding_model):
    interns = _make_interns(client, 4, prefix="pool")
    # First commit consumes these interns into a team.
    client.post(
        "/team-formation/commit",
        json={"intern_ids": [i["id"] for i in interns], "team_size": 4},
    )
    # A second call with no intern_ids should find nobody left unassigned.
    response = client.post("/team-formation/preview", json={})
    assert response.status_code == 409
