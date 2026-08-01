from app import models
from tests.factories import make_team


def test_success_probability_404_for_unknown_team(client):
    assert client.get("/success-probability/team/9999").status_code == 404


def test_success_probability_409_when_team_has_no_members(client, db_session):
    team = make_team(db_session, "Empty Success Team")
    assert client.get(f"/success-probability/team/{team.id}").status_code == 409


def test_success_probability_returns_probability_and_features(client, db_session):
    intern = client.post(
        "/interns", json={"full_name": "SP Dev", "email": "spr1@example.com", "attendance_pct": 90.0}
    ).json()
    team = make_team(db_session, "SP Team", member_ids=[intern["id"]])

    response = client.get(f"/success-probability/team/{team.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["team_id"] == team.id
    assert 0.0 <= body["success_probability"] <= 100.0
    assert "team_balance" in body["features"]

    # Day 11: Explainable AI Layer — SHAP-based explanation attached.
    explanation = body["explanation"]
    assert isinstance(explanation["base_value"], float)
    assert len(explanation["factors"]) == 3
    assert all(f["direction"] in ("increased", "decreased", "neutral") for f in explanation["factors"])
    assert explanation["reasons"]
    assert explanation["summary"]


def test_success_probability_recalculate_persists_to_team(client, db_session):
    intern = client.post(
        "/interns", json={"full_name": "SP Dev2", "email": "spr2@example.com", "attendance_pct": 90.0}
    ).json()
    team = make_team(db_session, "SP Team 2", member_ids=[intern["id"]])

    response = client.post(f"/success-probability/team/{team.id}/recalculate")
    assert response.status_code == 200
    body = response.json()

    db_session.expire_all()
    team_row = db_session.get(models.Team, team.id)
    assert team_row.success_probability == body["success_probability"] / 100.0
