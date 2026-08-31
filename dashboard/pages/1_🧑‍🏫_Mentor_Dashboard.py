"""
Day 12 — Mentor Dashboard. Day 14 — switched to lib/ui.py's shared
loading/error helpers (see that module's docstring for why). Post-Day-20
— re-themed (lib/theme.py) and risk badges now use a shared severity
color instead of only an emoji.

Everything here is one view over the Day 10 `/recommend-teams` response
(plus one supplementary call to Day 6's `/compatibility/team/{id}` for the
pairwise breakdown, which `/recommend-teams` intentionally doesn't inline
per-pair — only the team average — to keep that response from ballooning
with O(n²) pairs per team). Nothing is computed here; this page only
renders what the backend already calculated.
"""
import pandas as pd
import streamlit as st

from lib.api_client import get_json, post_json
from lib.theme import apply_theme, risk_color
from lib.ui import action_error, fetch_error, loading

st.set_page_config(page_title="Mentor Dashboard", page_icon="🧑‍🏫", layout="wide")
apply_theme()

st.title(" Mentor Dashboard")
st.caption("Recommended Teams · Team Balance Analysis · Collaboration Score · Suggested Changes")


# ---------------------------------------------------------------------------
# Controls — form a candidate pool and run /recommend-teams
# ---------------------------------------------------------------------------

with loading("Loading interns..."):
    ok, interns = get_json("/interns")
if not ok:
    fetch_error(interns)
    st.stop()

with st.form("recommend_teams_form"):
    st.subheader("Form recommended teams")

    available_labels = {f'{i["full_name"]} (#{i["id"]})': i["id"] for i in interns}
    selected_labels = st.multiselect(
        "Candidate interns (leave empty to use the default available/unassigned pool)",
        options=list(available_labels.keys()),
    )
    col1, col2 = st.columns(2)
    with col1:
        team_size = st.number_input("Team size", min_value=1, value=4, step=1)
    with col2:
        algorithm = st.selectbox("Algorithm", ["kmeans", "agglomerative"])

    submitted = st.form_submit_button("Recommend teams", type="primary")

if submitted:
    intern_ids = [available_labels[label] for label in selected_labels]
    with loading("Running clustering + all six engines..."):
        ok, result = post_json(
            "/recommend-teams",
            {"intern_ids": intern_ids, "team_size": int(team_size), "algorithm": algorithm},
        )
    if not ok:
        action_error("form teams", result)
    else:
        st.session_state["recommend_result"] = result

result = st.session_state.get("recommend_result")

if not result:
    st.info("Configure the candidate pool above and click **Recommend teams** to get started.")
    st.stop()

st.success(
    f"Formed {len(result['teams'])} team(s) with **{result['algorithm']}** "
    f"({result['archetype_count']} skill archetypes). "
    f"{len(result['unassigned_intern_ids'])} intern(s) left unassigned."
)

# ---------------------------------------------------------------------------
# One expandable section per recommended team
# ---------------------------------------------------------------------------

for team in result["teams"]:
    header = (
        f"{team['name']}  —  overall {team['overall_score']:.0f}/100  "
        f"·  led by {team['suggested_leader_name']}"
    )
    with st.expander(header, expanded=False):
        member_df = pd.DataFrame(team["members"])
        col_members, col_scores = st.columns([2, 1])

        with col_members:
            st.markdown("**Members**")
            st.dataframe(member_df, use_container_width=True, hide_index=True)

        with col_scores:
            st.metric("Compatibility", f"{team['compatibility_score']:.0f}/100")
            st.metric("Success probability", f"{team['success_probability']:.0f}%")
            st.metric("Diversity (team balance)", f"{team['diversity_score']:.2f}")

        st.divider()

        # --- Team Balance Analysis ---
        st.markdown("**Team Balance Analysis**")
        if team["skill_matrix"]:
            skill_df = pd.DataFrame(team["skill_matrix"])[["skill_name", "intern_count", "avg_proficiency"]]
            st.bar_chart(skill_df.set_index("skill_name")["intern_count"])
            st.caption(
                f"Diversity score {team['diversity_score']:.2f} — higher means less overlap "
                "across members' skill sets. The chart shows how many members hold each skill; "
                "a flatter, wider spread is what a balanced team looks like."
            )
        else:
            st.caption("No skill data available for this team.")

        st.divider()

        # --- Collaboration Score (Day 6 pairwise breakdown) ---
        st.markdown("**Collaboration Score**")
        pair_ok, pair_data = get_json(f"/compatibility/team/{team['id']}")
        if not pair_ok:
            st.caption(f"Pairwise breakdown unavailable: {pair_data}")
        elif not pair_data["pairs"]:
            st.caption("Not enough members for a pairwise breakdown.")
        else:
            pair_rows = []
            for p in pair_data["pairs"]:
                a_name = next((m["full_name"] for m in team["members"] if m["intern_id"] == p["intern_a_id"]), p["intern_a_id"])
                b_name = next((m["full_name"] for m in team["members"] if m["intern_id"] == p["intern_b_id"]), p["intern_b_id"])
                pair_rows.append({"Pair": f"{a_name} ↔ {b_name}", "Score": p["total_score"]})
            pair_df = pd.DataFrame(pair_rows).sort_values("Score")
            st.dataframe(pair_df, use_container_width=True, hide_index=True)
            weakest = pair_df.iloc[0]
            st.caption(f"Weakest pair: **{weakest['Pair']}** ({weakest['Score']:.0f}/100) — worth a closer look.")

        st.divider()

        # --- Project fit ---
        st.markdown("**Recommended project**")
        if team["project"]:
            p = team["project"]
            st.write(f"**{p['title']}** ({p['difficulty_level']}) — coverage {p['coverage_score'] * 100:.0f}%")
            c1, c2, c3 = st.columns(3)
            c1.caption(f" Matched: {', '.join(p['matched_skills']) or '—'}")
            c2.caption(f" Missing: {', '.join(p['missing_skills']) or '—'}")
            c3.caption(f" Extra: {', '.join(p['extra_skills']) or '—'}")

            if team["workload"]:
                st.markdown("**Workload distribution**")
                workload_df = pd.DataFrame(team["workload"])[
                    ["full_name", "role", "assigned_skills", "suggested_responsibility"]
                ]
                st.dataframe(workload_df, use_container_width=True, hide_index=True)
        else:
            st.caption("No project matched this team yet (no coverage against any listed project).")

        st.divider()

        # --- Suggested Changes: risks (Day 9) + SHAP explanation reasons (Day 11) ---
        st.markdown("**Suggested changes**")
        if team["risks"]:
            for risk in team["risks"]:
                color = risk_color(risk["severity"])
                label = risk["type"].replace("_", " ").title()
                st.markdown(
                    f'<div style="border-left: 3px solid {color}; padding: 4px 10px; '
                    f'margin-bottom: 6px; background-color: rgba(255,255,255,0.03);">'
                    f'<span style="color: {color}; font-weight: 600;">{label}</span> — '
                    f'<span style="color: var(--text-muted);">{risk["message"]}</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown("No risks flagged for this team.")

        with st.popover("Why this success probability?"):
            st.write(team["explanation"]["summary"])
            for reason in team["explanation"]["reasons"]:
                st.markdown(f"- {reason}")

if result["unassigned_intern_ids"]:
    st.subheader("Unassigned")
    st.write(result["unassigned_intern_ids"])
