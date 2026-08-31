def test_generate_embedding_for_one_intern(client, fake_embedding_model):
    intern = client.post("/interns", json={"full_name": "Ada", "email": "ada2@example.com"}).json()

    response = client.post(f"/embeddings/interns/{intern['id']}/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["intern_id"] == intern["id"]
    assert body["dimensions"] == 384
    assert len(body["embedding"]) == 384


def test_generate_embedding_404_for_unknown_intern(client, fake_embedding_model):
    response = client.post("/embeddings/interns/99999/generate")
    assert response.status_code == 404


def test_get_embedding_409_before_generation(client):
    intern = client.post("/interns", json={"full_name": "B", "email": "b2@example.com"}).json()
    response = client.get(f"/embeddings/interns/{intern['id']}")
    assert response.status_code == 409


def test_get_embedding_after_generation(client, fake_embedding_model):
    intern = client.post("/interns", json={"full_name": "C", "email": "c2@example.com"}).json()
    client.post(f"/embeddings/interns/{intern['id']}/generate")

    response = client.get(f"/embeddings/interns/{intern['id']}")

    assert response.status_code == 200
    assert response.json()["dimensions"] == 384


def test_generate_all_reports_summary(client, fake_embedding_model):
    client.post("/interns", json={"full_name": "D", "email": "d2@example.com"})
    client.post("/interns", json={"full_name": "E", "email": "e2@example.com"})

    response = client.post("/embeddings/generate-all")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    # both were already auto-embedded on create, so a plain generate-all should hit cache
    assert body["skipped_cached"] == 2


def test_embedding_status_reflects_coverage(client, fake_embedding_model):
    client.post("/interns", json={"full_name": "F", "email": "f2@example.com"})

    response = client.get("/embeddings/status")

    assert response.status_code == 200
    statuses = response.json()
    assert len(statuses) == 1
    assert statuses[0]["has_embedding"] is True
