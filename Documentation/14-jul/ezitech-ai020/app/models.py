"""
Day 1 ERD — draft schema for the AI Team Formation & Project Allocation Engine.

Entities: Intern, Skill, InternSkill (junction), Project, Team, TeamMember (junction),
TeamHistory, MentorFeedback, Attendance.

This is a DRAFT: Day 2 turns it into real Alembic migrations. Expect small field
changes as the AI engines (Week 2) reveal what data they actually need.
"""

from datetime import date, datetime

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class Intern(Base):
    __tablename__ = "interns"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)

    technology_stack = Column(String(255))       # e.g. "React, Node.js, MongoDB"
    github_url = Column(String(255))
    github_contributions = Column(Integer, default=0)   # commit/PR count, refreshed periodically

    case_study_performance = Column(Float, default=0.0)  # avg score across case studies
    engineering_credits = Column(Integer, default=0)
    attendance_pct = Column(Float, default=100.0)         # rolling aggregate; daily detail in Attendance

    leadership_score = Column(Float, default=0.0)         # 0-10, derived + mentor-rated
    communication_score = Column(Float, default=0.0)      # 0-10

    is_available = Column(Boolean, default=True)
    project_interests = Column(String(255))       # comma-separated tech/domain interests (MVP; normalize later if needed)

    created_at = Column(DateTime, default=datetime.utcnow)

    skills = relationship("InternSkill", back_populates="intern", cascade="all, delete-orphan")
    team_memberships = relationship("TeamMember", back_populates="intern")
    feedback_entries = relationship("MentorFeedback", back_populates="intern")
    attendance_logs = relationship("Attendance", back_populates="intern")
    team_history = relationship("TeamHistory", back_populates="intern")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), unique=True, nullable=False)     # e.g. "React", "FastAPI", "Docker"
    category = Column(String(50))                              # "Language" | "Framework" | "Tool" | "Domain"

    interns = relationship("InternSkill", back_populates="skill")


class InternSkill(Base):
    """Many-to-many: an intern has a proficiency level in a given skill."""
    __tablename__ = "intern_skills"
    __table_args__ = (UniqueConstraint("intern_id", "skill_id", name="uq_intern_skill"),)

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    proficiency = Column(Integer, default=1)   # 1 (beginner) - 5 (expert)

    intern = relationship("Intern", back_populates="skills")
    skill = relationship("Skill", back_populates="interns")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    description = Column(Text)
    required_tech_stack = Column(String(255))   # comma-separated for MVP; e.g. "Laravel, MySQL, Vue"
    difficulty_level = Column(String(20), default="Medium")   # "Easy" | "Medium" | "Hard"

    teams = relationship("Team", back_populates="project")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    compatibility_score = Column(Float, default=0.0)     # 0-100, from Collaboration Prediction Model
    success_probability = Column(Float, default=0.0)     # 0-1, from Performance Analytics Engine
    risk_notes = Column(Text)                             # populated by Risk Analysis module

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="teams")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """Many-to-many: which interns are on which team, and in what role."""
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "intern_id", name="uq_team_intern"),)

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    role = Column(String(30), default="Member")    # "Lead" | "Member"
    suggested_responsibility = Column(String(255))  # from Workload Distribution logic

    team = relationship("Team", back_populates="members")
    intern = relationship("Intern", back_populates="team_memberships")


class TeamHistory(Base):
    """Previous team history — an input signal for future team formation."""
    __tablename__ = "team_history"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    past_team_name = Column(String(100))
    past_project_title = Column(String(150))
    outcome_rating = Column(Float)   # 0-10, how well that past team performed

    intern = relationship("Intern", back_populates="team_history")


class MentorFeedback(Base):
    __tablename__ = "mentor_feedback"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    mentor_name = Column(String(100))
    score = Column(Float)          # 0-10
    comments = Column(Text)
    given_on = Column(Date, default=date.today)

    intern = relationship("Intern", back_populates="feedback_entries")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    log_date = Column(Date, default=date.today)
    present = Column(Boolean, default=True)

    intern = relationship("Intern", back_populates="attendance_logs")
