"""
Day 13 — Admin Dashboard. Day 14 — switched to lib/ui.py's shared
loading/error helpers (see that module's docstring for why).

Four views, per the execution guide: cross-team analytics, project success
rates, technology distribution, resource utilization. The first three come
from the Day 13 backend `/admin-analytics/*` endpoints (built alongside
this page); technology distribution deliberately calls Day 4's existing
`GET /skill-matrix/technology-frequency` (no team_id = org-wide) instead of
duplicating that aggregation — same "reuse what already computes this"
approach the Mentor Dashboard took with `/compatibility/team/{id}` on Day 12.

Charts use Plotly (the guide's first-listed option for the Admin
Dashboard), rendered via `st.plotly_chart`.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from lib.api_client import get_json
from lib.ui import empty_state, fetch_error, loading

st.set_page_config(page_title="Admin Dashboard", page_icon="🛠️", layout="wide")

st.title("🛠️ Admin Dashboard")
st.caption("Cross-Team Analytics · Project Success Rates · Technology Distribution · Resource Utilization")


# ---------------------------------------------------------------------------
# Cross-Team Analytics
# ---------------------------------------------------------------------------

st.subheader("Cross-Team Analytics")

with loading("Loading cross-team analytics..."):
    ok, teams_data = get_json("/admin-analytics/teams")
if not ok:
    fetch_error(teams_data)
    st.stop()

if teams_data["team_count"] == 0:
    empty_state("No teams yet — form some via the Mentor Dashboard or POST /teams.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total teams", teams_data["team_count"])
    c2.metric(
        "Avg compatibility",
        f"{teams_data['avg_compatibility_score']:.0f}/100" if teams_data["avg_compatibility_score"] is not None else "—",
    )
    c3.metric(
        "Avg success probability",
        f"{teams_data['avg_success_probability']:.0f}%" if teams_data["avg_success_probability"] is not None else "—",
    )
    c4.metric("Flagged at risk", f"{teams_data['teams_flagged_at_risk']} / {teams_data['teams_assessed_for_risk']} assessed")

    col_size, col_project = st.columns(2)
    with col_size:
        size_df = pd.DataFrame(
            [{"Team size": k, "Teams": v} for k, v in teams_data["size_distribution"].items()]
        ).sort_values("Team size")
        fig = px.bar(size_df, x="Team size", y="Teams", title="Team size distribution")
        st.plotly_chart(fig, use_container_width=True)
    with col_project:
        project_status_df = pd.DataFrame([
            {"Status": "With project", "Teams": teams_data["teams_with_project"]},
            {"Status": "Without project", "Teams": teams_data["teams_without_project"]},
        ])
        fig = px.pie(project_status_df, names="Status", values="Teams", title="Project assignment status")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**All teams**")
    team_df = pd.DataFrame(teams_data["teams"])
    st.dataframe(
        team_df.rename(columns={
            "team_name": "Team", "member_count": "Members", "compatibility_score": "Compatibility",
            "success_probability": "Success %", "project_title": "Project",
            "risk_assessed": "Risk assessed", "flagged_at_risk": "Flagged",
        }).drop(columns=["team_id"]),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Project Success Rates
# ---------------------------------------------------------------------------

st.subheader("Project Success Rates")

with loading("Loading project success rates..."):
    ok, project_data = get_json("/admin-analytics/projects")
if not ok:
    fetch_error(project_data)
elif project_data["project_count"] == 0:
    empty_state("No projects yet.")
else:
    st.caption(
        f"{project_data['project_count']} project(s) · "
        f"{project_data['projects_without_teams']} with no team matched yet"
    )
    matched = [p for p in project_data["projects"] if p["team_count"] > 0]
    if matched:
        matched_df = pd.DataFrame(matched)
        fig = px.bar(
            matched_df, x="title", y="team_count",
            color="avg_success_probability", color_continuous_scale="Blues",
            labels={"title": "Project", "team_count": "Teams matched", "avg_success_probability": "Avg success %"},
            title="Teams matched per project (colored by avg success probability)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No project has a matched team yet — run team formation + project matching first.")

    st.dataframe(
        pd.DataFrame(project_data["projects"]).rename(columns={
            "title": "Project", "difficulty_level": "Difficulty", "team_count": "Teams matched",
            "avg_success_probability": "Avg success %", "avg_compatibility_score": "Avg compatibility",
        }).drop(columns=["project_id"]),
        use_container_width=True, hide_index=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Technology Distribution (reuses Day 4's org-wide skill-matrix endpoint)
# ---------------------------------------------------------------------------

st.subheader("Technology Distribution")

with loading("Loading technology distribution..."):
    ok, tech_data = get_json("/skill-matrix/technology-frequency")
if not ok:
    fetch_error(tech_data)
elif not tech_data["frequency"]:
    empty_state("No skill/technology data yet — import or create some interns first.")
else:
    tech_df = pd.DataFrame(
        [{"Technology": k, "Interns": v} for k, v in tech_data["frequency"].items()]
    ).sort_values("Interns", ascending=False).head(20)
    fig = px.bar(
        tech_df, x="Interns", y="Technology", orientation="h",
        title=f"Top technologies across {tech_data['intern_count']} interns",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Resource Utilization
# ---------------------------------------------------------------------------

st.subheader("Resource Utilization")

with loading("Loading resource utilization..."):
    ok, util = get_json("/admin-analytics/resource-utilization")
if not ok:
    fetch_error(util)
elif util["total_interns"] == 0:
    empty_state("No interns yet.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total interns", util["total_interns"])
    c2.metric("Assigned", f"{util['assigned_count']} ({util['assigned_pct']:.0f}%)")
    c3.metric("Available candidate pool", util["available_and_unassigned_count"])
    c4.metric("With embedding", util["with_embedding_count"])

    col_assign, col_avg = st.columns(2)
    with col_assign:
        assign_df = pd.DataFrame([
            {"Status": "Assigned", "Interns": util["assigned_count"]},
            {"Status": "Unassigned", "Interns": util["unassigned_count"]},
        ])
        fig = px.pie(assign_df, names="Status", values="Interns", title="Team assignment status")
        st.plotly_chart(fig, use_container_width=True)
    with col_avg:
        avg_df = pd.DataFrame([
            {"Metric": "Avg attendance %", "Value": util["avg_attendance_pct"]},
            {"Metric": "Avg case study score", "Value": util["avg_case_study_performance"]},
            {"Metric": "Avg engineering credits", "Value": util["avg_engineering_credits"]},
        ])
        fig = px.bar(avg_df, x="Metric", y="Value", title="Org-wide averages")
        st.plotly_chart(fig, use_container_width=True)
