"""
Post-Day-20 design pass — shared visual identity for the dashboard.

## Why this exists

Before this pass, `dashboard/` ran on Streamlit's stock light theme —
functionally complete (see lib/ui.py's docstring) but visually generic,
and disconnected from `presentation/AI-020_Technical_Presentation.pptx`,
which already has a real, deliberate visual identity. A mentor watching
the deck and then opening the live dashboard during a demo would be
looking at two unrelated products. This module fixes that by giving the
dashboard the *same* design system as the deck, not a fresh one.

## Design plan (frontend-design skill process — plan, then build)

**Subject.** This is not a marketing page — it's an internal engineering
console. Three audiences (mentor, admin, student) come here to act on
AI-computed team data with full traceability: which team, why that score,
what to change. The design has to read as "instrumentation for a working
system," not "product landing page."

**Color — reused verbatim from the deck, not re-chosen.** Extracted
directly from `presentation/.../ppt/theme/*.xml` and every slide's
`srgbClr` values (grep-counted: `24406B` appears 228 times, `17C3B2` 64
times, etc. — these are the deck's actual working palette, not a
guess):

    --bg-deep      #0A1830   page background
    --bg-surface   #132A4C   card / panel background
    --bg-raised    #1B3B66   hover state, alternating table rows
    --border       #24406B   dividers, card borders            (228 uses in the deck)
    --accent       #17C3B2   primary actions, metrics, links     (64 uses in the deck)
    --text         #E9EFF7   primary text                        (62 uses in the deck)
    --text-muted   #7C93B3   captions, labels, secondary text    (20 uses in the deck)

This is a deliberate reuse, not the "dark background + one bright accent"
default the frontend-design skill warns about picking without a reason —
the reason here is that this exact palette already is this project's
brand, established in the deck, and cross-deliverable consistency is the
whole point.

**Type.** IBM Plex Sans for headers/body, IBM Plex Mono for every number
that came out of a computed engine (scores, percentages, counts, IDs).
Plex was designed by IBM specifically for technical/engineering
documentation — it fits an "engineering console" subject on purpose,
rather than defaulting to Inter or the system font stack. Putting scores
in mono specifically (not just body text) is the same instinct as the
deck's own "not marketing round numbers" caption on the stats slide —
mono reads as "measured," proportional reads as "written."

**Layout.** Streamlit's own component set stays — re-skinning it is the
pragmatic choice for a 3-role internal tool (matches this project's
running "simplest tool that satisfies the requirement" theme), not a
custom component library. Every touchpoint (sidebar, metrics, buttons,
tables, expanders, inputs, alerts) is re-themed via the CSS below so nothing
reads as stock Streamlit.

**Signature.** A literal node/edge network visualization of the
Engineering Knowledge Graph (see `render_skill_network` below), used on
the Admin Dashboard. Nothing else in the product visualizes a graph, and
it's not decoration — it's the actual shape of the one engine that had no
frontend surface at all until this pass.

## Where this applies, and a caveat

`apply_theme()` is called once per page, right after `st.set_page_config`.
It does two things: injects a `<style>` block (works regardless of how
the app is launched) and — best-effort — a `.streamlit/config.toml`
sitting next to this file's Docker `WORKDIR` (`dashboard/`, per
`docker-compose.yml`'s `build: ./dashboard`) sets Streamlit's *native*
widget theme so the CSS injection isn't fighting Streamlit's own defaults
on load. If you run `streamlit run dashboard/Home.py` from the repo root
instead of `cd dashboard && streamlit run Home.py`, Streamlit won't find
that config.toml (it only checks the current working directory) — the
CSS injection still applies either way, so the visual result is nearly
identical, but for the config.toml theme to apply too, run from inside
`dashboard/`.

This was built and CSS-reviewed against Streamlit 1.38's DOM (the pinned
version in `dashboard/requirements.txt`) but could not be rendered in a
browser during this pass — no network access in that sandbox to install
`streamlit` itself. Visual QA (`streamlit run dashboard/Home.py`, look at
every page) is still owed before this is called final — see
DEMO_SCRIPT.md's "Setup" section, now updated to say so.
"""
import streamlit as st

BG_DEEP = "#0A1830"
BG_SURFACE = "#132A4C"
BG_RAISED = "#1B3B66"
BORDER = "#24406B"
ACCENT = "#17C3B2"
TEXT = "#E9EFF7"
TEXT_MUTED = "#7C93B3"

RISK_HIGH = "#EF4444"
RISK_MEDIUM = "#F5B841"
RISK_OK = ACCENT


def apply_theme() -> None:
    """Call once per page, immediately after st.set_page_config(...)."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        :root {{
            --bg-deep: {BG_DEEP};
            --bg-surface: {BG_SURFACE};
            --bg-raised: {BG_RAISED};
            --border: {BORDER};
            --accent: {ACCENT};
            --text: {TEXT};
            --text-muted: {TEXT_MUTED};
        }}

        html, body, [class*="css"] {{
            font-family: "IBM Plex Sans", sans-serif;
        }}

        /* Page + main container */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
            background-color: var(--bg-deep);
            color: var(--text);
        }}
        [data-testid="stHeader"] {{
            background-color: var(--bg-deep);
        }}

        /* Sidebar */
        [data-testid="stSidebar"] {{
            background-color: #081222;
            border-right: 1px solid var(--border);
        }}
        [data-testid="stSidebar"] * {{
            color: var(--text) !important;
        }}

        /* Headings */
        h1, h2, h3, h4 {{
            color: var(--text) !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em;
        }}
        p, span, label, .stMarkdown, .stCaption {{
            color: var(--text);
        }}
        [data-testid="stCaptionContainer"], .stCaption, small {{
            color: var(--text-muted) !important;
        }}

        /* Dividers */
        hr {{
            border-color: var(--border) !important;
        }}

        /* Metrics — the deck's own "stat card" language, reused here */
        [data-testid="stMetric"] {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 16px 18px;
        }}
        [data-testid="stMetricValue"] {{
            font-family: "IBM Plex Mono", monospace !important;
            color: var(--accent) !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: var(--text-muted) !important;
        }}

        /* Buttons */
        .stButton > button {{
            background-color: var(--accent);
            color: var(--bg-deep);
            border: none;
            border-radius: 8px;
            font-weight: 600;
        }}
        .stButton > button:hover {{
            background-color: #1DDDC9;
            color: var(--bg-deep);
        }}
        .stButton > button[kind="secondary"] {{
            background-color: transparent;
            color: var(--accent);
            border: 1px solid var(--accent);
        }}

        /* Inputs */
        .stTextInput input, .stNumberInput input,
        [data-baseweb="select"] > div, .stMultiSelect [data-baseweb="select"] > div {{
            background-color: var(--bg-surface) !important;
            border: 1px solid var(--border) !important;
            color: var(--text) !important;
            border-radius: 8px !important;
        }}

        /* Expanders (used as the Mentor Dashboard's per-team cards) */
        [data-testid="stExpander"] {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border) !important;
            border-radius: 10px;
        }}
        [data-testid="stExpander"] summary {{
            color: var(--text) !important;
            font-weight: 500;
        }}

        /* Dataframes / tables */
        [data-testid="stDataFrame"] {{
            border: 1px solid var(--border);
            border-radius: 8px;
        }}

        /* Alerts (empty_state / fetch_error / action_error in lib/ui.py) */
        [data-testid="stAlert"] {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text);
        }}

        /* Forms */
        [data-testid="stForm"] {{
            background-color: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 12px 16px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def risk_color(severity: str) -> str:
    """Consistent risk-severity color, reused anywhere a page shows a risk
    badge (currently only the Mentor Dashboard, but centralized so a
    future page doesn't invent its own severity palette)."""
    return {"high": RISK_HIGH, "medium": RISK_MEDIUM}.get(severity, RISK_OK)


def render_skill_network(nodes: list[dict], edges: list[tuple[str, str]], title: str) -> None:
    """The signature element (see this module's docstring): a literal
    node/edge visualization of a slice of the Engineering Knowledge Graph
    (app/services/knowledge_graph_service.py), using a deterministic
    circular layout — good enough for the handful-of-nodes slices this
    renders (one skill's interns, or one intern's recommended
    collaborators), not intended for the whole-org graph.

    `nodes`: [{"id": str, "label": str, "kind": "intern"|"skill"}, ...]
    `edges`: [(source_id, target_id), ...]
    """
    import math

    import plotly.graph_objects as go

    if not nodes:
        st.caption("Not enough graph data yet to draw a network.")
        return

    n = len(nodes)
    positions = {
        node["id"]: (math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
        for i, node in enumerate(nodes)
    }

    edge_x, edge_y = [], []
    for source, target in edges:
        if source in positions and target in positions:
            x0, y0 = positions[source]
            x1, y1 = positions[target]
            edge_x += [x0, x1, None]
            edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=1, color=BORDER), hoverinfo="none",
    )

    node_x = [positions[node["id"]][0] for node in nodes]
    node_y = [positions[node["id"]][1] for node in nodes]
    node_color = [ACCENT if node["kind"] == "intern" else TEXT_MUTED for node in nodes]
    node_size = [26 if node["kind"] == "intern" else 18 for node in nodes]

    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=[node["label"] for node in nodes],
        textposition="bottom center",
        textfont=dict(color=TEXT, family="IBM Plex Sans", size=12),
        marker=dict(size=node_size, color=node_color, line=dict(width=2, color=BG_DEEP)),
        hoverinfo="text",
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=dict(text=title, font=dict(color=TEXT, family="IBM Plex Sans", size=15)),
        showlegend=False,
        plot_bgcolor=BG_DEEP,
        paper_bgcolor=BG_DEEP,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=40, b=10),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)
