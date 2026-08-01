"""Day 14 — /student endpoint (Student Dashboard).

Single read-only endpoint: everything one student needs to see about
themselves in one call, rather than making the dashboard stitch together
/interns/{id}, /teams/{id}, and /workload/team/{id} itself.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.services import student_dashboard_service

router = APIRouter(prefix="/student", tags=["student-dashboard"])


@router.get("/{intern_id}/dashboard", response_model=schemas.StudentDashboardOut)
def student_dashboard(intern_id: int, db: Session = Depends(get_db)):
    """Assigned team, role, compatibility score, strengths, and
    responsibilities for one intern. `team` is null if this intern hasn't
    been placed on a team yet — that's a normal state, not an error."""
    intern = InternRepository(db).get_by_id_with_team_context(intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")

    # An intern could in principle be on more than one TeamMember row (no
    # DB constraint forbids it beyond one row per team), but every engine
    # in this system — Team Formation's default candidate pool, Workload,
    # Risk Analysis — treats "assigned" as a single team. Taking the first
    # membership keeps the dashboard consistent with that assumption
    # instead of inventing multi-team semantics nothing else supports.
    team_member = intern.team_memberships[0] if intern.team_memberships else None
    team_view = student_dashboard_service.build_team_view(team_member) if team_member else None

    return schemas.StudentDashboardOut(
        intern_id=intern.id,
        full_name=intern.full_name,
        is_available=intern.is_available,
        strengths=student_dashboard_service.identify_strengths(intern),
        top_skills=[
            schemas.StudentSkillHighlightOut(**s)
            for s in student_dashboard_service.top_skills(intern)
        ],
        team=schemas.StudentTeamOut(**team_view) if team_view else None,
    )
