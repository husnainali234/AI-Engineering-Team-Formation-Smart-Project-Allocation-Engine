from tests.factories import make_intern, make_team


def test_team_chemistry_404_for_unknown_team(client):
    response = client.get("/team-chemistry/team/999999")
    assert response.status_code == 404


def test_team_chemistry_returns_score_label_and_components(client, db_session):
    a = make_intern(db_session, email="rtc1@example.com", leadership_score=8.0)
    b = make_intern(db_session, email="rtc2@example.com", leadership_score=3.0)
    team = make_team(db_session, "Chemistry Team", member_ids=[a.id, b.id])

    response = client.get(f"/team-chemistry/team/{team.id}")
    assert response.status_code == 200
    body = response.json()

    assert body["team_id"] == team.id
    assert body["team_name"] == "Chemistry Team"
    assert body["member_count"] == 2
    assert 0.0 <= body["chemistry_score"] <= 100.0
    assert body["label"] in ("Strong", "Workable", "Fragile")
    assert set(body["components"].keys()) == {
        "leadership_balance", "shared_interests", "communication_spread", "feedback_sentiment",
    }
    for component in body["components"].values():
        assert set(component.keys()) == {"raw_score", "weight", "contribution"}


def test_team_chemistry_reflects_current_membership_not_a_stale_snapshot(client, db_session):
    solo_leader = make_intern(db_session, email="rtc3@example.com", leadership_score=9.0)
    co_leader = make_intern(db_session, email="rtc4@example.com", leadership_score=9.0)
    team = make_team(db_session, "Live Team", member_ids=[solo_leader.id])

    before = client.get(f"/team-chemistry/team/{team.id}").json()

    from app import models
    db_session.add(models.TeamMember(team_id=team.id, intern_id=co_leader.id, role="Member"))
    db_session.commit()

    after = client.get(f"/team-chemistry/team/{team.id}").json()

    assert before["member_count"] == 1
    assert after["member_count"] == 2
    assert after["components"]["leadership_balance"]["raw_score"] < before["components"]["leadership_balance"]["raw_score"]
