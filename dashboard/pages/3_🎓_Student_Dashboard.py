"""
Day 14 — Student Dashboard.

Single call to the Day 14 `GET /student/{id}/dashboard` endpoint, which
already assembles everything this page shows (team, role, scores,
strengths, responsibilities) — this page only renders it, the same
"backend computes, dashboard displays" split the Mentor and Admin pages
follow. Uses lib/ui.py's shared loading/error helpers, same as those two.
"""
import streamlit as st

from lib.api_client import get_json
from lib.ui import empty_state, fetch_error, loading

st.set_page_config(page_title="Student Dashboard", page_icon="🎓", layout="wide")

st.title("🎓 Student Dashboard")
st.caption("Your Team · Role · Compatibility Score · Strengths · Responsibilities")

st.subheader("Find yourself")
intern_id = st.number_input("Your intern ID", min_value=1, step=1, value=1)
look_up = st.button("Look me up", type="primary")

if not look_up:
    empty_state("Enter your intern ID above and click **Look me up** to see your dashboard.")
    st.stop()

with loading("Loading your dashboard..."):
    ok, dashboard = get_json(f"/student/{intern_id}/dashboard")

if not ok:
    fetch_error(dashboard)
    st.stop()

st.success(f"Welcome, **{dashboard['full_name']}**!")

team = dashboard["team"]

if not team:
    empty_state(
        "You haven't been placed on a team yet. Check back after the next "
        "team formation run, or ask your mentor."
    )
else:
    st.subheader(f"Your team: {team['team_name']}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Your role", team["role"])
    c2.metric("Compatibility score", f"{team['compatibility_score']:.0f}/100")
    c3.metric("Success probability", f"{team['success_probability']:.0f}%")

    if team["project_title"]:
        st.markdown(f"**Project:** {team['project_title']}")
    else:
        st.caption("No project assigned to your team yet.")

    st.markdown("**Your responsibility**")
    if team["suggested_responsibility"]:
        st.info(team["suggested_responsibility"])
    else:
        empty_state("Not assigned yet — your mentor hasn't finalized workload distribution for your team.")

    st.markdown("**Teammates**")
    if team["teammates"]:
        for name in team["teammates"]:
            st.markdown(f"- {name}")
    else:
        st.caption("You're currently the only member on this team.")

st.divider()

st.subheader("Your strengths")
if dashboard["strengths"]:
    for strength in dashboard["strengths"]:
        st.markdown(f"- {strength}")
else:
    empty_state(
        "No standout signals yet — strengths show up here once your "
        "attendance, case study, leadership, or GitHub activity data builds up."
    )

if dashboard["top_skills"]:
    st.markdown("**Top skills**")
    for skill in dashboard["top_skills"]:
        st.markdown(f"- {skill['skill_name']} ({skill['proficiency']}/5)")
