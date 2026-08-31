"""
Day 14 — Student Dashboard. Post-Day-20 — re-themed (lib/theme.py) and
gained a "People to work with next" panel, the personal-scale frontend
surface for the Engineering Knowledge Graph
(app/services/knowledge_graph_service.py) — the org-wide, pick-a-skill
version lives on the Admin Dashboard's new Skill Network section.

Single call to the Day 14 `GET /student/{id}/dashboard` endpoint, which
already assembles everything this page shows (team, role, scores,
strengths, responsibilities) — this page only renders it, the same
"backend computes, dashboard displays" split the Mentor and Admin pages
follow. Uses lib/ui.py's shared loading/error helpers, same as those two.
"""
import streamlit as st

from lib.api_client import get_json
from lib.theme import apply_theme
from lib.ui import empty_state, fetch_error, loading

st.set_page_config(page_title="Student Dashboard", page_icon="🎓", layout="wide")
apply_theme()

st.title("Student Dashboard")
st.caption("Your Team · Role · Compatibility Score · Strengths · Responsibilities · People to Work With Next")

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

st.divider()

# ---------------------------------------------------------------------------
# People to work with next (post-Day-20 — Engineering Knowledge Graph,
# app/services/knowledge_graph_service.py). Graph-native, so every card
# below carries the actual evidence it was ranked from (shared skills,
# past-team outcome) rather than an opaque score.
# ---------------------------------------------------------------------------

st.subheader("People to work with next")
st.caption(
    "Ranked by shared skills and, where it exists, how a past team you "
    "were both on scored — from the Engineering Knowledge Graph, not the "
    "compatibility engine above."
)

with loading("Finding your graph connections..."):
    collab_ok, collaborators = get_json(f"/knowledge-graph/intern/{intern_id}/recommended-collaborators")

if not collab_ok:
    fetch_error(collaborators)
elif not collaborators:
    empty_state("No graph connections yet — add some skills or team history to see suggestions here.")
else:
    cols = st.columns(min(3, len(collaborators)))
    for i, person in enumerate(collaborators):
        with cols[i % len(cols)]:
            past = person["past_collaboration"]
            past_line = (
                f"Worked together on **{past['past_team_name']}** "
                f"({past['outcome_rating']:.0f}/10)"
                if past else "No shared team history yet"
            )
            st.markdown(
                f"""<div style="background-color: var(--bg-surface); border: 1px solid var(--border);
                border-radius: 10px; padding: 14px 16px; margin-bottom: 10px;">
                <div style="font-family: 'IBM Plex Mono', monospace; color: var(--accent); font-size: 1.4rem;">
                    #{person['intern_id']}
                </div>
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-top: 4px;">
                    Shared skills: {', '.join(person['shared_skills']) or '—'}
                </div>
                <div style="color: var(--text-muted); font-size: 0.85rem; margin-top: 2px;">
                    {past_line}
                </div>
                </div>""",
                unsafe_allow_html=True,
            )
