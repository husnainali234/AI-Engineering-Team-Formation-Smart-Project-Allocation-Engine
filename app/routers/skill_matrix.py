"""Day 4 — /skill-matrix endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.team_repository import TeamRepository
from app.services import skill_matrix_service

router = APIRouter(prefix="/skill-matrix", tags=["skill-matrix"])


@router.get("/team/{team_id}", response_model=schemas.TeamSkillMatrixOut)
def team_skill_matrix(team_id: int, db: Session = Depends(get_db)):
    """The full per-skill table (frequency + proficiency stats + which
    interns hold it) for one team — the 'Team Skill Matrix' from the spec."""
    team = TeamRepository(db).get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    members = InternRepository(db).list_by_team(team_id)
    rows = skill_matrix_service.build_skill_matrix(members)

    return schemas.TeamSkillMatrixOut(
        team_id=team.id,
        team_name=team.name,
        member_count=len(members),
        skills=rows,
    )


@router.get("/technology-frequency", response_model=schemas.TechnologyFrequencyOut)
def technology_frequency(
    team_id: int | None = Query(default=None, description="Restrict to one team; omit for org-wide frequency"),
    db: Session = Depends(get_db),
):
    """Headcount per skill/technology — how many interns (in scope) know
    it at all, no proficiency involved. Org-wide by default; pass team_id
    to scope to one team."""
    if team_id is not None:
        if not TeamRepository(db).get_by_id(team_id):
            raise HTTPException(status_code=404, detail="Team not found")
        interns = InternRepository(db).list_by_team(team_id)
        scope = f"team:{team_id}"
    else:
        interns = InternRepository(db).list_all_with_skills()
        scope = "global"

    return schemas.TechnologyFrequencyOut(
        scope=scope,
        intern_count=len(interns),
        frequency=skill_matrix_service.technology_frequency(interns),
    )


@router.get("/proficiency-aggregation", response_model=schemas.ProficiencyAggregationOut)
def proficiency_aggregation(
    team_id: int | None = Query(default=None, description="Restrict to one team; omit for org-wide aggregation"),
    db: Session = Depends(get_db),
):
    """avg/min/max proficiency (1-5) per skill, computed only from
    structured InternSkill rows (proficiency has no meaning for a
    technology_stack-only mention). Org-wide by default; pass team_id to
    scope to one team."""
    if team_id is not None:
        if not TeamRepository(db).get_by_id(team_id):
            raise HTTPException(status_code=404, detail="Team not found")
        interns = InternRepository(db).list_by_team(team_id)
        scope = f"team:{team_id}"
    else:
        interns = InternRepository(db).list_all_with_skills()
        scope = "global"

    return schemas.ProficiencyAggregationOut(
        scope=scope,
        aggregation=skill_matrix_service.proficiency_aggregation(interns),
    )
