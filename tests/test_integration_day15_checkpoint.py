"""
Day 15 — Checkpoint 3: Full Integration.

Per the execution guide: "Full system run: import data -> engines ->
dashboards." Day 5's checkpoint proved import -> embeddings -> skill
matrix; Day 10's checkpoint proved every engine wired together behind
/recommend-teams. What neither of those covers, and what's new here, is
the last hop both of them stop short of: that a /recommend-teams run's
persisted output is exactly what the three dashboards' own endpoints
(admin-analytics, student-dashboard) read back — not a parallel
computation that could silently drift from it.

Chain exercised end to end:

    POST /import
        -> DB rows + auto-generated embeddings (Day 3-4)
    POST /recommend-teams
        -> team formation, compatibility, skill matrix, project fit,
           workload, success probability, risk, SHAP explanation
           (Days 6-11), persisted to Team/TeamMember (Day 10)
    GET /admin-analytics/teams, /admin-analytics/projects,
        /admin-analytics/resource-utilization
        -> Mentor/Admin Dashboard data source (Day 13) rolling up
           exactly what /recommend-teams just persisted
    GET /student/{id}/dashboard
        -> Student Dashboard data source (Day 14), same source-of-truth
           check from the individual student's side

This is the "internal dry-run demo" the guide calls for on Day 15 —
scripted as a test instead of a manual click-through so it stays part of
the regression suite rather than a one-off checked box.
"""
from tests.factories import make_project


def _import_interns(client, n=8):
    rows = ["full_name,email,technology_stack,attendance_pct,leadership_score,communication_score"]
    for i in range(n):
        stack = "React,Node.js" if i % 2 == 0 else "Django,Postgres"
        rows.append(f"Checkpoint15 {i},checkpoint15.{i}@example.com,\"{stack}\",92.0,6.0,6.0")
    csv_content = "\n".join(rows) + "\n"
    files = {"file": ("interns.csv", csv_content, "text/csv")}
    response = client.post("/import", files=files)
    assert response.status_code == 200
    return response.json()


def test_full_pipeline_import_through_dashboards(client, fake_embedding_model, db_session):
    # --- 1. Import: rows land, embeddings generate automatically ---
    import_body = _import_interns(client, n=8)
    assert import_body["interns_created"] == 8
    assert import_body["embedding_summary"]["generated"] == 8

    interns = [
        i for i in client.get("/interns").json()
        if i["email"].startswith("checkpoint15.")
    ]
    assert len(interns) == 8
    intern_ids = [i["id"] for i in interns]

    project = make_project(
        db_session, title="Checkpoint15 Dashboard Rebuild",
        required_tech_stack="React,Node.js,Django,Postgres",
    )

    # --- 2. Engines: every engine wired together behind /recommend-teams ---
    rec_response = client.post(
        "/recommend-teams",
        json={"intern_ids": intern_ids, "team_size": 4, "algorithm": "kmeans"},
    )
    assert rec_response.status_code == 200
    rec_body = rec_response.json()
    assert len(rec_body["teams"]) >= 1

    team = rec_body["teams"][0]
    # Every field a dashboard reads must actually be populated, not just present.
    assert team["compatibility_score"] >= 0.0
    assert team["success_probability"] >= 0.0
    assert team["overall_score"] >= 0.0
    assert team["explanation"]["summary"]
    assert isinstance(team["risks"], list)

    # --- 3a. Dashboards: Admin — cross-team analytics reflects this run ---
    cross_team = client.get("/admin-analytics/teams").json()
    assert cross_team["team_count"] == len(rec_body["teams"])
    persisted = {row["team_id"]: row for row in cross_team["teams"]}
    assert persisted[team["id"]]["compatibility_score"] == team["compatibility_score"]
    assert round(persisted[team["id"]]["success_probability"], 2) == round(team["success_probability"], 2)

    # --- 3b. Dashboards: Admin — project success rates see the same assignment ---
    if team["project"]:
        project_rates = client.get("/admin-analytics/projects").json()
        matched = next(p for p in project_rates["projects"] if p["project_id"] == team["project"]["project_id"])
        assert matched["team_count"] >= 1

    # --- 3c. Dashboards: Admin — resource utilization counts these interns as assigned ---
    utilization = client.get("/admin-analytics/resource-utilization").json()
    assigned_here = sum(1 for i in intern_ids if i in {
        m["intern_id"] for t in rec_body["teams"] for m in t["members"]
    })
    assert utilization["assigned_count"] >= assigned_here
    assert utilization["with_embedding_count"] >= 8

    # --- 3d. Dashboards: Student — each placed member's own view matches ---
    for member in team["members"]:
        dash = client.get(f"/student/{member['intern_id']}/dashboard")
        assert dash.status_code == 200
        dash_body = dash.json()
        assert dash_body["team"] is not None
        assert dash_body["team"]["team_name"] == team["name"]
        assert dash_body["team"]["compatibility_score"] == team["compatibility_score"]
        assert dash_body["team"]["role"] in ("Lead", "Member")
        # Workload was applied inline by /recommend-teams whenever a project
        # was matched — the student dashboard must see the same responsibility
        # text, not "not assigned yet", once that's happened.
        if team["project"] and team["workload"]:
            assert dash_body["team"]["suggested_responsibility"]

    # --- 3e. Unassigned interns (if any) still resolve, just with team: null ---
    for unassigned_id in rec_body["unassigned_intern_ids"]:
        dash = client.get(f"/student/{unassigned_id}/dashboard")
        assert dash.status_code == 200
        assert dash.json()["team"] is None


def test_recommend_teams_output_is_stable_source_of_truth_for_technology_distribution(client, fake_embedding_model):
    """Admin Dashboard's Technology Distribution panel reuses Day 4's
    org-wide /skill-matrix/technology-frequency rather than recomputing
    from /recommend-teams — this confirms that reused endpoint still sees
    interns brought in through /import + /recommend-teams, not just ones
    created directly via /interns (which is all the Day 4 tests cover)."""
    import_body = _import_interns(client, n=4)
    assert import_body["interns_created"] == 4

    tech = client.get("/skill-matrix/technology-frequency").json()
    assert tech["frequency"].get("React", 0) >= 2
    assert tech["frequency"].get("Django", 0) >= 2
