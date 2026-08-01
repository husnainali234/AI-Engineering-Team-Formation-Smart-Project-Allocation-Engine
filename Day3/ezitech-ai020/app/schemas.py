"""
Day 3 — Pydantic schemas (request/response contracts) for the CRUD + /import endpoints.

Naming convention used throughout:
    <Entity>Base    -> shared fields
    <Entity>Create  -> what the client sends to create one
    <Entity>Update  -> what the client sends to patch one (all fields optional)
    <Entity>Out     -> what the API returns (adds id + server-generated fields)

Kept intentionally flat/MVP (no nested skill objects on Intern yet) — that gets
layered on Day 4 once the Skill Matrix / embeddings logic needs it.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


# ---------------------------------------------------------------------------
# Intern
# ---------------------------------------------------------------------------

class InternBase(BaseModel):
    full_name: str
    email: EmailStr
    technology_stack: Optional[str] = None
    github_url: Optional[str] = None
    github_contributions: int = 0
    case_study_performance: float = 0.0
    engineering_credits: int = 0
    attendance_pct: float = 100.0
    leadership_score: float = 0.0
    communication_score: float = 0.0
    is_available: bool = True
    project_interests: Optional[str] = None


class InternCreate(InternBase):
    pass


class InternUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    technology_stack: Optional[str] = None
    github_url: Optional[str] = None
    github_contributions: Optional[int] = None
    case_study_performance: Optional[float] = None
    engineering_credits: Optional[int] = None
    attendance_pct: Optional[float] = None
    leadership_score: Optional[float] = None
    communication_score: Optional[float] = None
    is_available: Optional[bool] = None
    project_interests: Optional[str] = None


class InternOut(InternBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    required_tech_stack: Optional[str] = None
    difficulty_level: str = "Medium"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_tech_stack: Optional[str] = None
    difficulty_level: Optional[str] = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------------------------------------------------------------------------
# Team + TeamMember
# ---------------------------------------------------------------------------

class TeamMemberBase(BaseModel):
    intern_id: int
    role: str = "Member"
    suggested_responsibility: Optional[str] = None


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberOut(TeamMemberBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int


class TeamBase(BaseModel):
    name: str
    project_id: Optional[int] = None
    compatibility_score: float = 0.0
    success_probability: float = 0.0
    risk_notes: Optional[str] = None


class TeamCreate(TeamBase):
    member_ids: list[int] = []   # convenience: create a team + members in one call


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    project_id: Optional[int] = None
    compatibility_score: Optional[float] = None
    success_probability: Optional[float] = None
    risk_notes: Optional[str] = None


class TeamOut(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    members: list[TeamMemberOut] = []


# ---------------------------------------------------------------------------
# /import
# ---------------------------------------------------------------------------

class ImportSummary(BaseModel):
    """Returned by POST /import — mirrors what a real portal-sync job would report."""
    source_format: str          # "csv" | "json"
    rows_received: int
    interns_created: int
    interns_updated: int
    rows_skipped: int
    errors: list[str] = []
