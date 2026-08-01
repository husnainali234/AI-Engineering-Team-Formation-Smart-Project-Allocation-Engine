from tests.factories import make_team


def test_risk_analysis_404_for_unknown_team(client):
    assert client.get("/risk-analysis/team/9999").status_code == 404


def test_risk_analysis_409_when_team_has_no_members(client, db_session):
    team = make_team(db_session, "Empty Risk Team")
    assert client.get(f"/risk-analysis/team/{team.id}").status_code == 409


def test_risk_analysis_flags_low_attendance_member(client, db_session):
    weak = client.post(
        "/interns",
        json={
            "full_name": "Weak Attendance",
            "email": "rar1@example.com",
            "technology_stack": "React",
            "leadership_score": 8.0,
            "attendance_pct": 30.0,
        },
    ).json()
    strong = client.post(
        "/interns",
        json={
            "full_name": "Strong Attendance",
            "email": "rar2@example.com",
            "technology_stack": "Django",
            "leadership_score": 8.0,
            "attendance_pct": 95.0,
        },
    ).json()
    team = make_team(db_session, "Risk Team", member_ids=[weak["id"], strong["id"]], compatibility_score=90.0)

    response = client.get(f"/risk-analysis/team/{team.id}")
    assert response.status_code == 200
    types = {r["type"] for r in response.json()["risks"]}
    assert "low_attendance" in types


def test_risk_analysis_recalculate_persists_risk_notes(client, db_session):
    intern = client.post(
        "/interns",
        json={
            "full_name": "Solo Dev",
            "email": "rar3@example.com",
            "technology_stack": "React",
            "leadership_score": 2.0,
            "attendance_pct": 95.0,
        },
    ).json()
    team = make_team(db_session, "Risk Team 2", member_ids=[intern["id"]], compatibility_score=90.0)

    response = client.post(f"/risk-analysis/team/{team.id}/recalculate")
    assert response.status_code == 200

    team_out = client.get(f"/teams/{team.id}").json()
    assert team_out["risk_notes"]
    assert "leadership_gap" in team_out["risk_notes"]
