"""
Day 11 — shared backend API client for the dashboard.

Deliberately a thin `requests` wrapper, not a generated client — the
dashboard only ever calls a handful of endpoints (and more will be added
Days 12-14), so a small hand-written client is simpler to read and debug
than wiring up codegen from the OpenAPI schema for a Streamlit app this
size.
"""
import os

import requests

# In docker-compose, the dashboard container reaches the backend via the
# service name ("backend"); running the dashboard locally with
# `streamlit run dashboard/Home.py` against a locally-running API, it's
# just localhost. Overridable via env var either way.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

_DEFAULT_TIMEOUT = 5


def get_health() -> tuple[bool, str]:
    """Returns (is_healthy, detail_message) — used by Home.py's
    connectivity check and safe to call from any page."""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=_DEFAULT_TIMEOUT)
        response.raise_for_status()
        return True, str(response.json())
    except requests.RequestException as exc:
        return False, str(exc)


def get_json(path: str, params: dict | None = None) -> tuple[bool, dict | list | str]:
    """GET helper for the placeholder/preview calls the role pages make.
    Returns (ok, payload_or_error_message) rather than raising, so a page
    can render a friendly message instead of a stack trace when the
    backend isn't running yet."""
    try:
        response = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=_DEFAULT_TIMEOUT)
        response.raise_for_status()
        return True, response.json()
    except requests.RequestException as exc:
        return False, str(exc)


def post_json(path: str, json_body: dict | None = None, timeout: int = 30) -> tuple[bool, dict | list | str]:
    """POST helper — used for /recommend-teams, which can take longer than
    a plain GET (clustering + six engines running per team), hence the
    separate, longer default timeout."""
    try:
        response = requests.post(f"{BACKEND_URL}{path}", json=json_body or {}, timeout=timeout)
        if not response.ok:
            # Surface the backend's own `detail` message (404/409/422) rather
            # than a generic HTTP error string, since that's the actionable
            # part for whoever's looking at the dashboard.
            try:
                return False, response.json().get("detail", response.text)
            except ValueError:
                return False, response.text
        return True, response.json()
    except requests.RequestException as exc:
        return False, str(exc)
