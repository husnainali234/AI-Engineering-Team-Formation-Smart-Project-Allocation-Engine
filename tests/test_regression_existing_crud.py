"""
Regression coverage for Day 1-3 functionality, run against the Day 4-6
codebase. Not a rewrite of Day 3's own test plan — just enough to prove the
new automatic-embedding hooks in interns.py/import_data.py never break the
CRUD contract, even when the embedding model itself is unavailable.
"""


def test_create_intern_succeeds_even_without_ml_model_available(client):
    """No fake_embedding_model fixture here on purpose: sentence-transformers
    isn't installed in this test environment, so the automatic embedding
    hook will fail internally — CRUD must still return 201."""
    response = client.post("/interns", json={"full_name": "Ada Lovelace", "email": "ada@example.com"})

    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"


def test_full_crud_lifecycle_still_works(client):
    create = client.post("/interns", json={"full_name": "Grace Hopper", "email": "grace@example.com"})
    assert create.status_code == 201
    intern_id = create.json()["id"]

    get_resp = client.get(f"/interns/{intern_id}")
    assert get_resp.status_code == 200

    update_resp = client.put(f"/interns/{intern_id}", json={"leadership_score": 9.5})
    assert update_resp.status_code == 200
    assert update_resp.json()["leadership_score"] == 9.5

    list_resp = client.get("/interns")
    assert list_resp.status_code == 200
    assert any(i["id"] == intern_id for i in list_resp.json())

    delete_resp = client.delete(f"/interns/{intern_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/interns/{intern_id}")
    assert missing_resp.status_code == 404


def test_duplicate_email_still_rejected(client):
    client.post("/interns", json={"full_name": "A", "email": "dup@example.com"})
    second = client.post("/interns", json={"full_name": "B", "email": "dup@example.com"})
    assert second.status_code == 409


def test_project_crud_unaffected(client):
    create = client.post("/projects", json={"title": "Test Project", "difficulty_level": "Easy"})
    assert create.status_code == 201

    list_resp = client.get("/projects")
    assert list_resp.status_code == 200


def test_team_crud_unaffected(client):
    intern = client.post("/interns", json={"full_name": "Team Member", "email": "tm@example.com"}).json()

    create = client.post("/teams", json={"name": "Alpha", "member_ids": [intern["id"]]})
    assert create.status_code == 201
    assert len(create.json()["members"]) == 1


def test_import_csv_still_works_without_ml_model(client):
    csv_content = "full_name,email,technology_stack\nJohn Doe,john@example.com,React\n"
    files = {"file": ("interns.csv", csv_content, "text/csv")}

    response = client.post("/import", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["interns_created"] == 1
    assert body["rows_skipped"] == 0
