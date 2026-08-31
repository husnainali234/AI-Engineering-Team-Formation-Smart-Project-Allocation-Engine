def test_summary_reflects_created_interns(client):
    client.post("/interns", json={"full_name": "A", "email": "kga@example.com", "technology_stack": "Laravel"})
    client.post("/interns", json={"full_name": "B", "email": "kgb@example.com", "technology_stack": "Laravel"})

    response = client.get("/knowledge-graph/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["nodes_by_type"]["intern"] == 2
    assert body["nodes_by_type"]["skill"] == 1
    assert body["edges_by_relation"]["HAS_SKILL"] == 2


def test_interns_with_skill_endpoint(client):
    client.post("/interns", json={"full_name": "A", "email": "kgc@example.com", "technology_stack": "Laravel"})
    client.post("/interns", json={"full_name": "B", "email": "kgd@example.com", "technology_stack": "MERN"})

    response = client.get("/knowledge-graph/skill/Laravel/interns")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1


def test_interns_with_skill_endpoint_empty_for_unknown_skill(client):
    response = client.get("/knowledge-graph/skill/Cobol/interns")
    assert response.status_code == 200
    assert response.json() == []


def test_recommended_collaborators_404_for_unknown_intern(client):
    response = client.get("/knowledge-graph/intern/9999/recommended-collaborators")
    assert response.status_code == 404


def test_recommended_collaborators_returns_shared_skill_evidence(client):
    a = client.post(
        "/interns", json={"full_name": "A", "email": "kge@example.com", "technology_stack": "React, Node.js"}
    ).json()
    client.post(
        "/interns", json={"full_name": "B", "email": "kgf@example.com", "technology_stack": "React, Node.js"}
    )

    response = client.get(f"/knowledge-graph/intern/{a['id']}/recommended-collaborators")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert set(body[0]["shared_skills"]) == {"React", "Node.js"}


def test_path_404_for_unknown_intern(client):
    a = client.post("/interns", json={"full_name": "A", "email": "kgg@example.com"}).json()
    response = client.get(f"/knowledge-graph/path?intern_a_id={a['id']}&intern_b_id=9999")
    assert response.status_code == 404


def test_path_found_via_shared_skill(client):
    a = client.post(
        "/interns", json={"full_name": "A", "email": "kgh@example.com", "technology_stack": "Laravel"}
    ).json()
    b = client.post(
        "/interns", json={"full_name": "B", "email": "kgi@example.com", "technology_stack": "Laravel"}
    ).json()

    response = client.get(f"/knowledge-graph/path?intern_a_id={a['id']}&intern_b_id={b['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["length"] == 2


def test_path_not_found_when_disconnected(client):
    a = client.post(
        "/interns", json={"full_name": "A", "email": "kgj@example.com", "technology_stack": "Laravel"}
    ).json()
    b = client.post(
        "/interns", json={"full_name": "B", "email": "kgk@example.com", "technology_stack": "COBOL"}
    ).json()

    response = client.get(f"/knowledge-graph/path?intern_a_id={a['id']}&intern_b_id={b['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["path"] == []
