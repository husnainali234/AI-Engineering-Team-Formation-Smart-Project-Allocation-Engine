"""
Day 14 — shared UI helpers for the dashboard.

Before today, each page rolled its own copy of the same three patterns:
a spinner around a fetch, an `st.error` for an unreachable backend, and an
`st.info` for "no data yet". Small enough that it worked, but the wording
and which calls got wrapped in a spinner had already started to drift
between the Day 12 Mentor page and the Day 13 Admin page. Centralizing
them here is today's "unify styling and loading states across all three
dashboards" — every page (including this one, Home.py) now calls these
instead of writing `st.spinner(...)` / `st.error(f"Could not reach...")`
inline.
"""
from contextlib import contextmanager

import streamlit as st

# One icon per role, reused anywhere a page needs to refer to another
# dashboard by name (e.g. Home.py's nav summary) instead of retyping the
# emoji + label pairing in more than one place.
PAGE_ICONS = {"mentor" , "admin" , "student" }


@contextmanager
def loading(message: str):
    """Thin wrapper around st.spinner — exists so every page's loading
    copy goes through one place instead of each page phrasing its own."""
    with st.spinner(message):
        yield


def fetch_error(payload) -> None:
    """Standard error rendering for a failed get_json call — same wording
    every dashboard page uses for an unreachable backend."""
    st.error(f"Could not reach the backend: {payload}")


def action_error(action: str, payload) -> None:
    """Standard error rendering for a failed post_json call — same shape
    as fetch_error but for "the action itself failed" (e.g. a 409/422
    from the backend) rather than "couldn't reach the backend at all"."""
    st.error(f"Could not {action}: {payload}")


def empty_state(message: str) -> None:
    """Standard 'nothing here yet' rendering — st.info with consistent
    phrasing instead of each page writing its own variant."""
    st.info(message)
