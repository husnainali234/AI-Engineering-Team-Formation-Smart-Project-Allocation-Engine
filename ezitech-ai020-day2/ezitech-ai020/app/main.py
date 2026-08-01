from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

app = FastAPI(
    title="Ezitech AI-020: Team Formation & Project Allocation Engine",
    description="AI-powered engine that forms balanced engineering teams and recommends projects.",
    version="0.1.0",
)

# Wide open for local dev; tighten before deployment (Week 4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["meta"])
def root():
    return {"service": "AI-020 Team Formation Engine", "status": "running"}


@app.get("/health", tags=["meta"])
def health(db: Session = Depends(get_db)):
    """Confirms the API is up AND can reach Postgres."""
    db.execute(text("SELECT 1"))
    return {"api": "ok", "database": "ok"}


# Routers for /interns, /projects, /teams, /import get wired in on Day 3.
