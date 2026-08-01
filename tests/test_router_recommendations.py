def test_recommendations_404_for_unknown_intern(client):
    assert client.get("/recommendations/interns/9999").status_code == 404


def test_recommendations_409_without_embedding(client):
    intern = client.post("/interns", json={"full_name": "A", "email": "a11@example.com"}).json()
    assert client.get(f"/recommendations/interns/{intern['id']}").status_code == 409


def test_recommendations_blends_similarity_and_compatibility(client, fake_embedding_model):
    target = client.post(
        "/interns", json={"full_name": "Target", "email": "target11@example.com", "technology_stack": "React"}
    ).json()
    client.post(
        "/interns", json={"full_name": "Candidate", "email": "cand11@example.com", "technology_stack": "React"}
    )

    response = client.get(f"/recommendations/interns/{target['id']}")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    candidate = body[0]
    assert 0 <= candidate["compatibility_score"] <= 100
    assert -1 <= candidate["similarity_score"] <= 1
    assert "blended_rank_score" in candidate


def test_recommendations_respects_limit(client, fake_embedding_model):
    target = client.post("/interns", json={"full_name": "Target", "email": "target12@example.com"}).json()
    for i in range(3):
        client.post("/interns", json={"full_name": f"C{i}", "email": f"c{i}12@example.com"})

    response = client.get(f"/recommendations/interns/{target['id']}?limit=2")

    assert response.status_code == 200
    assert len(response.json()) == 2
