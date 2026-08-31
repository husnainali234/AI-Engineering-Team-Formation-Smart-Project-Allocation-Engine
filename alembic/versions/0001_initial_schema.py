"""initial schema: interns, skills, intern_skills, projects, teams,
team_members, team_history, mentor_feedback, attendance

Revision ID: 0001
Revises:
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- interns -----------------------------------------------------
    op.create_table(
        "interns",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False, unique=True),
        sa.Column("technology_stack", sa.String(length=255), nullable=True),
        sa.Column("github_url", sa.String(length=255), nullable=True),
        sa.Column("github_contributions", sa.Integer(), server_default="0"),
        sa.Column("case_study_performance", sa.Float(), server_default="0.0"),
        sa.Column("engineering_credits", sa.Integer(), server_default="0"),
        sa.Column("attendance_pct", sa.Float(), server_default="100.0"),
        sa.Column("leadership_score", sa.Float(), server_default="0.0"),
        sa.Column("communication_score", sa.Float(), server_default="0.0"),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true()),
        sa.Column("project_interests", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    # --- skills --------------------------------------------------------
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("category", sa.String(length=50), nullable=True),
    )

    # --- projects --------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required_tech_stack", sa.String(length=255), nullable=True),
        sa.Column("difficulty_level", sa.String(length=20), server_default="Medium"),
    )

    # --- intern_skills (junction) ---------------------------------------
    op.create_table(
        "intern_skills",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("intern_id", sa.Integer(), sa.ForeignKey("interns.id"), nullable=False),
        sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("proficiency", sa.Integer(), server_default="1"),
        sa.UniqueConstraint("intern_id", "skill_id", name="uq_intern_skill"),
    )

    # --- teams -----------------------------------------------------------
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("compatibility_score", sa.Float(), server_default="0.0"),
        sa.Column("success_probability", sa.Float(), server_default="0.0"),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # --- team_members (junction) -----------------------------------------
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("intern_id", sa.Integer(), sa.ForeignKey("interns.id"), nullable=False),
        sa.Column("role", sa.String(length=30), server_default="Member"),
        sa.Column("suggested_responsibility", sa.String(length=255), nullable=True),
        sa.UniqueConstraint("team_id", "intern_id", name="uq_team_intern"),
    )

    # --- team_history ------------------------------------------------------
    op.create_table(
        "team_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("intern_id", sa.Integer(), sa.ForeignKey("interns.id"), nullable=False),
        sa.Column("past_team_name", sa.String(length=100), nullable=True),
        sa.Column("past_project_title", sa.String(length=150), nullable=True),
        sa.Column("outcome_rating", sa.Float(), nullable=True),
    )

    # --- mentor_feedback -----------------------------------------------------
    op.create_table(
        "mentor_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("intern_id", sa.Integer(), sa.ForeignKey("interns.id"), nullable=False),
        sa.Column("mentor_name", sa.String(length=100), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("given_on", sa.Date(), nullable=True),
    )

    # --- attendance -----------------------------------------------------------
    op.create_table(
        "attendance",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("intern_id", sa.Integer(), sa.ForeignKey("interns.id"), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=True),
        sa.Column("present", sa.Boolean(), server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_table("attendance")
    op.drop_table("mentor_feedback")
    op.drop_table("team_history")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.drop_table("intern_skills")
    op.drop_table("projects")
    op.drop_table("skills")
    op.drop_table("interns")
