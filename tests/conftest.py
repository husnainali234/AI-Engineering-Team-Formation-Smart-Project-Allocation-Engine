"""
Shared test fixtures for the Day 4-6 test suite.

Two things worth calling out:

1. DB: tests run against an in-memory SQLite DB, not the real Postgres from
   docker-compose. `Intern.skill_embedding` uses a generic SQLAlchemy `JSON`
   column (see app/models.py) specifically so this works — a Postgres-only
   ARRAY/vector column would make the whole app untestable without a running
   Postgres instance.

2. Embedding model: the real `sentence-transformers` model is never loaded
   in tests — it's a large, slow-to-download dependency and tests shouldn't
   need network access. `fake_embedding_model` monkeypatches
   `app.ml.embedding_model.get_model` with a tiny deterministic stand-in
   (hash of the text -> pseudo-random unit vector) so embedding-dependent
   code (caching, cosine similarity, ranking) is fully exercised without it.

3. MLflow (Day 17): tracking is disabled suite-wide by an autouse fixture
   below (`_disable_mlflow_tracking`) so the test run never writes an
   `mlruns/` directory as a side effect. `tests/test_mlflow_tracking.py`
   re-enables it locally (via monkeypatch + tmp_path) to test the tracking
   path itself.
"""
import hashlib

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import EMBEDDING_DIM


@pytest.fixture(autouse=True)
def _disable_mlflow_tracking(monkeypatch):
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_ENABLED", False)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class _FakeEmbeddingModel:
    """Deterministic stand-in for SentenceTransformer: same input text
    always -> same 384-dim unit vector, different text -> a different
    vector. Good enough to test caching, cosine similarity, and ranking
    logic without downloading real model weights."""

    def encode(self, text: str):
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        rng = np.random.default_rng(seed)
        vector = rng.normal(size=EMBEDDING_DIM)
        return vector / np.linalg.norm(vector)


@pytest.fixture()
def fake_embedding_model(monkeypatch):
    fake_model = _FakeEmbeddingModel()
    monkeypatch.setattr("app.ml.embedding_model.get_model", lambda: fake_model)
    monkeypatch.setattr("app.services.embedding_service.get_model", lambda: fake_model)
    return fake_model
