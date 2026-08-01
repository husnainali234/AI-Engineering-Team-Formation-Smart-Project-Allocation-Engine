"""
Day 11 — Dashboard scaffold, entry point. Days 12-14 — the three
role-based pages went from skeleton to fully built (Mentor: Day 12,
Admin: Day 13, Student: Day 14), each pulling from real backend
endpoints. Day 14 also unified loading/error rendering across all three
via lib/ui.py — this page now uses those helpers too.

Role-based navigation (Mentor / Admin / Student) that runs locally and
talks to the real backend. Streamlit's own file-based routing (the
`pages/` directory next to this file) is what gives the sidebar
navigation "for free" — no custom router needed, which matches this
project's running theme of using the simplest tool that satisfies the
requirement instead of hand-rolling one.

Run locally with:
    streamlit run dashboard/Home.py

Or via `docker-compose up`, once the `dashboard` service is running (see
docker-compose.yml).
"""
import streamlit as st

from lib.api_client import BACKEND_URL, get_health
from lib.ui import loading

st.set_page_config(
    page_title="Ezitech AI-020 — Team Formation & Project Allocation",
    page_icon="🧭",
    layout="wide",
)

st.title("🧭 Ezitech AI-020")
st.subheader("Team Formation & Project Allocation Engine — Dashboard")

st.markdown(
    """
Use the sidebar to switch between the three role-based views. Each one is a
different lens over the same underlying data — recommended teams, scores,
and explanations computed identically (Day 11's SHAP-based Explainable AI
Layer) — just surfaced differently per audience:

- **🧑‍🏫 Mentor Dashboard** — recommended teams, team balance analysis,
  collaboration scores, suggested changes.
- **🛠️ Admin Dashboard** — cross-team analytics, project success rates,
  technology distribution, resource utilization.
- **🎓 Student Dashboard** — your assigned team, role, compatibility score,
  strengths, responsibilities.
"""
)

st.divider()

st.subheader("Backend connectivity")
col1, col2 = st.columns([1, 3])
with col1:
    check = st.button("Check backend health", type="primary")
with col2:
    st.caption(f"Target: `{BACKEND_URL}`")

if check:
    with loading("Pinging the API..."):
        ok, detail = get_health()
    if ok:
        st.success(f"Backend is reachable — {detail}")
    else:
        st.error(f"Backend is not reachable — {detail}")

st.divider()
st.caption(
    "Day 14 deliverable: all three dashboards complete and functioning "
    "end-to-end, wired to a live backend."
)
