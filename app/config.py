"""
Day 17 — Config cleanup.

Before this file, every module that needed an env var read it directly with
`os.getenv` at its own point of use (`app/database.py`'s `DATABASE_URL`,
`app/ml/embedding_model.py`'s `EMBEDDING_MODEL_NAME`) — workable at three
env vars, but Day 17 adds two more for MLflow, and "grep the codebase for
os.getenv to find every knob" doesn't scale. `pydantic-settings` has been
sitting in requirements.txt since Day 1 for exactly this, unused until now.

One `Settings` object, read once at import time, is the single source of
truth for every environment-driven value. Existing call sites
(`app/database.py`, `app/ml/embedding_model.py`) now read from `settings`
instead of calling `os.getenv` directly — same defaults as before, so this
is a pure refactor, not a behavior change.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---------------------------------------------------
    DATABASE_URL: str = "postgresql://ezitech:ezitech_pass@localhost:5432/ezitech_ai020"

    # --- Day 4: embeddings -------------------------------------------
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # --- Day 17: MLflow model-version tracking -----------------------
    # Local file store by default (`./mlruns`) — no MLflow server required
    # to get run history, params, and metrics; point this at a real
    # tracking server URI (e.g. "http://mlflow:5000") if one is ever stood
    # up without changing any application code.
    MLFLOW_TRACKING_URI: str = "file:./mlruns"
    MLFLOW_EXPERIMENT_NAME: str = "success-probability-model"
    # Tracking is best-effort and must never take the API down if the
    # tracking store isn't writable/reachable (see app/ml/mlflow_tracking.py).
    # Tests set this to false so the suite never touches disk for it.
    MLFLOW_TRACKING_ENABLED: bool = True

    # --- Day 18: deployment ------------------------------------------
    # Comma-separated list of allowed CORS origins. Defaults to "*" (wide
    # open, fine for local dev — see app/main.py's Day 1 note) so nothing
    # breaks for anyone still running docker-compose locally without a
    # .env change; a hosted demo (Day 18) sets this to the dashboard's
    # actual deployed origin instead of "*".
    ALLOWED_ORIGINS: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
