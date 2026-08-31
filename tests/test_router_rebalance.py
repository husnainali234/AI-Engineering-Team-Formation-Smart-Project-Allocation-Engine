from tests.factories import make_team


def _create_intern(client, **overrides):
    body = {
        "full_name": overrides.pop("full_name", "Rebalance Intern"),
        "email": overrides.pop("email"),
        "technology_stack": overrides.pop("technology_stack", "React, Node.js"),
        "is_available": overrides.pop("is_available", True),
    }
    body.update(overrides)
    response = client.post("/interns", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_rebalance_needed_empty_when_no_unavailable_members(client):
    response = client.get("/rebalance/needed")
    assert response.status_code == 200
    assert response.json() == {"teams": []}


def test_rebalance_needed_lists_teams_with_unavailable_members(client, fake_embedding_model, db_session):
    healthy = _create_intern(client, email="rb1@example.com")
    departing = _create_intern(client, email="rb2@example.com")

    team = make_team(db_session, "Rebalance Watch Team", member_ids=[healthy["id"], departing["id"]])

    client.put(f"/interns/{departing['id']}", json={"is_available": False})

    response = client.get("/rebalance/needed")
    assert response.status_code == 200
    body = response.json()
    assert body["teams"] == [
        {
            "team_id": team.id,
            "team_name": "Rebalance Watch Team",
            "unavailable_members": [{"intern_id": departing["id"], "full_name": departing["full_name"]}],
        }
    ]


def test_rebalance_team_404_for_unknown_team(client):
    response = client.post("/rebalance/team/999999")
    assert response.status_code == 404


def test_rebalance_team_409_when_nothing_to_rebalance(client, fake_embedding_model, db_session):
    healthy = _create_intern(client, email="rb3@example.com")
    team = make_team(db_session, "All Available Team", member_ids=[healthy["id"]])

    response = client.post(f"/rebalance/team/{team.id}")
    assert response.status_code == 409


def test_rebalance_team_swaps_unavailable_member_for_best_fit_replacement(
    client, fake_embedding_model, db_session
):
    from app import models

    staying = _create_intern(client, email="rb4@example.com")
    departing = _create_intern(client, email="rb5@example.com")
    close_candidate = _create_intern(client, email="rb6@example.com")
    far_candidate = _create_intern(client, email="rb7@example.com")

    # Override the fake model's hash-based (effectively random) vectors with
    # deterministic ones, so "best fit" has an unambiguous right answer.
    db_session.get(models.Intern, departing["id"]).skill_embedding = [1.0, 0.0]
    db_session.get(models.Intern, close_candidate["id"]).skill_embedding = [0.95, 0.05]
    db_session.get(models.Intern, far_candidate["id"]).skill_embedding = [0.0, 1.0]
    db_session.commit()

    team = make_team(db_session, "Swap Team", member_ids=[staying["id"], departing["id"]])
    client.put(f"/interns/{departing['id']}", json={"is_available": False})

    response = client.post(f"/rebalance/team/{team.id}")
    assert response.status_code == 200
    body = response.json()

    assert len(body["swaps"]) == 1
    swap = body["swaps"][0]
    assert swap["departing_intern_id"] == departing["id"]
    assert swap["replacement_intern_id"] == close_candidate["id"]

    member_ids = {m["intern_id"] for m in body["members"]}
    assert departing["id"] not in member_ids
    assert staying["id"] in member_ids
    assert close_candidate["id"] in member_ids

    # Replaced member is no longer available for a second team.
    all_interns = client.get("/interns").json()
    far_row = next(i for i in all_interns if i["id"] == far_candidate["id"])
    assert far_row["is_available"] is True  # untouched — wasn't the chosen replacement

    # Team was rescored, not just re-membered.
    assert "compatibility_score" in body
    assert 0.0 <= body["success_probability"] <= 100.0

    # No longer flagged, since the unavailable member is gone.
    still_needed = client.get("/rebalance/needed").json()
    assert team.id not in {t["team_id"] for t in still_needed["teams"]}


def test_rebalance_team_reassigns_leadership_when_leader_departs(client, fake_embedding_model, db_session):
    leader = _create_intern(client, email="rb8@example.com", leadership_score=9.0)
    member = _create_intern(client, email="rb9@example.com", leadership_score=2.0)
    replacement = _create_intern(client, email="rb10@example.com", leadership_score=3.0)

    team = make_team(db_session, "Leadership Swap Team", member_ids=[])
    db_session.refresh(team)
    from app import models

    db_session.add(models.TeamMember(team_id=team.id, intern_id=leader["id"], role="Lead"))
    db_session.add(models.TeamMember(team_id=team.id, intern_id=member["id"], role="Member"))
    db_session.commit()

    client.put(f"/interns/{leader['id']}", json={"is_available": False})

    response = client.post(f"/rebalance/team/{team.id}")
    assert response.status_code == 200
    body = response.json()

    leads = [m for m in body["members"] if m["role"] == "Lead"]
    assert len(leads) == 1
    assert leads[0]["intern_id"] != leader["id"]


def test_rebalance_team_leaves_member_in_place_when_no_replacement_available(
    client, fake_embedding_model, db_session
):
    departing = _create_intern(client, email="rb11@example.com")
    team = make_team(db_session, "No Candidates Team", member_ids=[departing["id"]])
    client.put(f"/interns/{departing['id']}", json={"is_available": False})

    response = client.post(f"/rebalance/team/{team.id}")
    assert response.status_code == 200
    body = response.json()

    assert body["swaps"][0]["replacement_intern_id"] is None
    # Still on the team — removing them with nothing to replace them would
    # just trade one problem for a worse one.
    assert any(m["intern_id"] == departing["id"] for m in body["members"])

    still_needed = client.get("/rebalance/needed").json()
    assert team.id in {t["team_id"] for t in still_needed["teams"]}
