from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Intern(Base):
    __tablename__ = "interns"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)

    technology_stack = Column(Text)
    github_url = Column(String(500))
    github_contributions = Column(Integer, default=0)

    case_study_performance = Column(Float, default=0.0)
    engineering_credits = Column(Integer, default=0)
    attendance_pct = Column(Float, default=0.0)

    leadership_score = Column(Float, default=0.0)
    communication_score = Column(Float, default=0.0)

    is_available = Column(Boolean, default=True)
    project_interests = Column(Text)

    skills = relationship(
        "InternSkill",
        back_populates="intern",
        cascade="all, delete-orphan",
    )

    mentor_feedback = relationship(
        "MentorFeedback",
        back_populates="intern",
        cascade="all, delete-orphan",
    )

    attendance_records = relationship(
        "Attendance",
        back_populates="intern",
        cascade="all, delete-orphan",
    )

    team_history = relationship(
        "TeamHistory",
        back_populates="intern",
        cascade="all, delete-orphan",
    )

    team_memberships = relationship(
        "TeamMember",
        back_populates="intern",
        cascade="all, delete-orphan",
    )


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100))

    interns = relationship(
        "InternSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
    )


class InternSkill(Base):
    __tablename__ = "intern_skills"

    id = Column(Integer, primary_key=True, index=True)

    intern_id = Column(Integer, ForeignKey("interns.id"), nullable=False)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)

    proficiency = Column(Integer, nullable=False)

    intern = relationship("Intern", back_populates="skills")
    skill = relationship("Skill", back_populates="interns")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text)

    required_tech_stack = Column(Text)
    difficulty_level = Column(String(50))

    teams = relationship(
        "Team",
        back_populates="project",
    )


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False)

    project_id = Column(Integer, ForeignKey("projects.id"))

    compatibility_score = Column(Float)
    success_probability = Column(Float)
    risk_notes = Column(Text)

    project = relationship("Project", back_populates="teams")

    members = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, index=True)

    team_id = Column(Integer, ForeignKey("teams.id"))
    intern_id = Column(Integer, ForeignKey("interns.id"))

    role = Column(String(100))
    suggested_responsibility = Column(Text)

    team = relationship("Team", back_populates="members")
    intern = relationship("Intern", back_populates="team_memberships")


class MentorFeedback(Base):
    __tablename__ = "mentor_feedback"

    id = Column(Integer, primary_key=True, index=True)

    intern_id = Column(Integer, ForeignKey("interns.id"))

    mentor_name = Column(String(255))
    score = Column(Float)
    comments = Column(Text)
    given_on = Column(Date)

    intern = relationship("Intern", back_populates="mentor_feedback")


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)

    intern_id = Column(Integer, ForeignKey("interns.id"))

    log_date = Column(Date)
    present = Column(Boolean, default=True)

    intern = relationship("Intern", back_populates="attendance_records")


class TeamHistory(Base):
    __tablename__ = "team_history"

    id = Column(Integer, primary_key=True, index=True)

    intern_id = Column(Integer, ForeignKey("interns.id"))

    past_team_name = Column(String(255))
    past_project_title = Column(String(255))
    outcome_rating = Column(Float)

    intern = relationship("Intern", back_populates="team_history")