"""
Day 5 — Checkpoint 1.

Verifies the full chain the spec calls out explicitly:

    Import Endpoint -> Database -> Embedding Engine -> Skill Matrix

i.e. that data landed via /import is queryable through the normal CRUD
endpoints, automatically gets embeddings without a separate manual step,
and immediately shows up correctly in the skill matrix / matching engines
built on top of it — end to end, not each piece in isolation.
"""
from tests.factories import make_team


def test_import_to_skill_matrix_full_pipeline(client, fake_embedding_model, db_session):
    csv_content = (
        "full_name,email,technology_stack\n"
        'Ada Lovelace,ada.checkpoint@example.com,"React,Node.js"\n'
        'Grace Hopper,grace.checkpoint@example.com,"React,Docker"\n'
    )
    files = {"file": ("interns.csv", csv_content, "text/csv")}

    # 1. Import works
    import_response = client.post("/import", files=files)
    assert import_response.status_code == 200
    import_body = import_response.json()
    assert import_body["interns_created"] == 2
    assert import_body["rows_skipped"] == 0

    # 2. Database: rows are queryable via the existing (Day 1-3) CRUD endpoint
    interns_response = client.get("/interns")
    assert interns_response.status_code == 200
    imported = [i for i in interns_response.json() if i["email"].endswith("checkpoint@example.com")]
    assert len(imported) == 2

    # 3. Embeddings generate automatically — no manual /embeddings/generate-all call
    assert import_body["embedding_summary"] is not None
    assert import_body["embedding_summary"]["generated"] == 2
    for intern in imported:
        status = client.get(f"/embeddings/interns/{intern['id']}")
        assert status.status_code == 200
        assert status.json()["dimensions"] == 384

    # 4. Skill Matrix returns correct values for the imported team
    team = make_team(db_session, "Checkpoint Team", member_ids=[i["id"] for i in imported])
    matrix_response = client.get(f"/skill-matrix/team/{team.id}")
    assert matrix_response.status_code == 200
    matrix_body = matrix_response.json()
    skills_by_name = {row["skill_name"]: row for row in matrix_body["skills"]}

    assert skills_by_name["React"]["intern_count"] == 2   # both imported rows had React
    assert skills_by_name["Node.js"]["intern_count"] == 1
    assert skills_by_name["Docker"]["intern_count"] == 1

    # And the matching engine can immediately act on the freshly-imported,
    # freshly-embedded data too (no separate warm-up step required).
    target_id = imported[0]["id"]
    recs = client.get(f"/matching/interns/{target_id}/recommendations")
    assert recs.status_code == 200
    assert len(recs.json()) == 1  # the other imported intern


def test_import_partial_failure_still_generates_embeddings_for_good_rows(client, fake_embedding_model):
    csv_content = (
        "full_name,email,technology_stack\n"
        "Valid Person,valid.checkpoint@example.com,Python\n"
        ",missing-name.checkpoint@example.com,Python\n"  # missing full_name -> should be skipped
    )
    files = {"file": ("interns.csv", csv_content, "text/csv")}

    response = client.post("/import", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["interns_created"] == 1
    assert body["rows_skipped"] == 1
    assert body["embedding_summary"]["total"] == 1
    assert body["embedding_summary"]["generated"] == 1
