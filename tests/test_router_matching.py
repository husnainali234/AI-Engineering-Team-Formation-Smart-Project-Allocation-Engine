def test_recommendations_404_for_unknown_intern(client):
    assert client.get("/matching/interns/9999/recommendations").status_code == 404


def test_recommendations_409_when_target_has_no_embedding(client):
    intern = client.post("/interns", json={"full_name": "A", "email": "a5@example.com"}).json()
    # No fake_embedding_model fixture -> auto-generation on create silently failed,
    # so this intern genuinely has no embedding yet.
    response = client.get(f"/matching/interns/{intern['id']}/recommendations")
    assert response.status_code == 409


def test_recommendations_returns_ranked_candidates(client, fake_embedding_model):
    target = client.post(
        "/interns", json={"full_name": "Target", "email": "target5@example.com", "technology_stack": "React"}
    ).json()
    client.post(
        "/interns", json={"full_name": "Candidate1", "email": "c1_5@example.com", "technology_stack": "React"}
    )
    client.post(
        "/interns", json={"full_name": "Candidate2", "email": "c2_5@example.com", "technology_stack": "Django"}
    )

    response = client.get(f"/matching/interns/{target['id']}/recommendations?limit=5")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert all("similarity_score" in c and "diversity_score" in c for c in body)


def test_complementary_matches_endpoint(client, fake_embedding_model):
    target = client.post(
        "/interns", json={"full_name": "Target", "email": "target6@example.com", "technology_stack": "React"}
    ).json()
    client.post(
        "/interns", json={"full_name": "Other", "email": "other6@example.com", "technology_stack": "Django"}
    )

    response = client.get(f"/matching/interns/{target['id']}/complementary?min_similarity=0.0")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_team_diversity_endpoint(client, fake_embedding_model, db_session):
    from tests.factories import assign_skill, make_skill, make_team
    from app import models

    intern_a = client.post("/interns", json={"full_name": "A", "email": "a6@example.com"}).json()
    intern_b = client.post("/interns", json={"full_name": "B", "email": "b6@example.com"}).json()

    react = make_skill(db_session, "React")
    django = make_skill(db_session, "Django")
    assign_skill(db_session, db_session.get(models.Intern, intern_a["id"]), react, proficiency=3)
    assign_skill(db_session, db_session.get(models.Intern, intern_b["id"]), django, proficiency=3)

    team = make_team(db_session, "Beta", member_ids=[intern_a["id"], intern_b["id"]])

    response = client.get(f"/matching/teams/{team.id}/diversity")

    assert response.status_code == 200
    assert response.json()["diversity_score"] == 1.0


def test_team_diversity_404_for_unknown_team(client):
    assert client.get("/matching/teams/9999/diversity").status_code == 404
