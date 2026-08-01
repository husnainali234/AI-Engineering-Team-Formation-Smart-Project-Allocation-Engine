"""
Day 4 — thin wrapper around the sentence-transformers model.

Model: all-MiniLM-L6-v2 (384-dim sentence embeddings). Chosen per the Day 4
spec: small (~80MB), fast on CPU, good general-purpose semantic quality —
appropriate for short skill/interest profile text, not long documents.

The import of `sentence_transformers` (and therefore torch) is deferred to
inside `get_model()` rather than done at module load time. Two reasons:

    1. Startup cost — most requests (plain CRUD) never touch the model, so
       the API shouldn't pay torch's import cost on every boot.
    2. Testability — unit tests can monkeypatch `get_model` without needing
       the (large) ML dependency stack installed at all.

The loaded model is cached process-wide (module-level singleton guarded by
a lock) so repeated calls — e.g. batch embedding generation across 100+
interns — pay the load cost once, not per-call.
"""
import logging
import threading
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Day 17: read from the centralized Settings object instead of os.getenv
# directly. Same env var name, same default.
EMBEDDING_MODEL_NAME = settings.EMBEDDING_MODEL_NAME

_model_lock = threading.Lock()
_model = None  # type: Optional["SentenceTransformer"]  # noqa: F821


def get_model():
    """Return the process-wide SentenceTransformer instance, loading it on
    first use. Thread-safe (double-checked locking) so concurrent requests
    during a cold start don't each try to load the model independently."""
    global _model

    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock
                logger.info("Loading sentence-transformers model %r", EMBEDDING_MODEL_NAME)
                from sentence_transformers import SentenceTransformer  # deferred import

                _model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    return _model


def is_model_loaded() -> bool:
    """Used by health/status endpoints to report whether the (potentially
    slow, first-call) model load has already happened, without triggering it."""
    return _model is not None
