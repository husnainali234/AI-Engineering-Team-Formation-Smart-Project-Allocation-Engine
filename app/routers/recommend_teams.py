"""
Day 10 — Checkpoint 2: /recommend-teams.

The single integration endpoint: forms teams (Day 7's clustering +
round-robin), then runs compatibility (Day 6), skill matrix (Day 4),
leadership (Day 7), project matching (Day 8), workload (Day 8), and
success probability + risk (Day 9) against each one — persisting every
result to the same Team/TeamMember rows each individual engine's own
endpoint would (Team.compatibility_score, Team.project_id,
Team.success_probability, Team.risk_notes, TeamMember.role,
TeamMember.suggested_responsibility).

Deliberately not "thin" like the single-engine routers — this IS the
integration layer the spec asks for on Day 10, so the orchestration lives
here rather than being hidden inside a service. The per-team computation
that doesn't need a persisted team (compatibility, skill matrix, project
fit, success probability, risk) is still pushed into
recommend_teams_service.compute_team_recommendation so it stays unit
testable without the DB.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services import recommend_teams_service, team_formation_service, workload_service

router = APIRouter(prefix="/recommend-teams", tags=["recommend-teams"])


def _resolve_candidates(request: schemas.TeamFormationRequest, intern_repo: InternRepository) -> list[models.Intern]:
    if request.intern_ids:
        candidates = intern_repo.list_by_ids(request.intern_ids)
        found_ids = {c.id for c in candidates}
        missing = [i for i in request.intern_ids if i not in found_ids]
        if missing:
            raise HTTPException(status_code=404, detail=f"Unknown intern_ids: {missing}")
        return candidates
    return intern_repo.list_available_unassigned_with_embeddings()


def _history_by_intern(team_repo: TeamRepository, candidates: list[models.Intern]) -> dict[int, list[models.TeamHistory]]:
    if not candidates:
        return {}
    history_by_intern: dict[int, list[models.TeamHistory]] = {}
    for h in team_repo.team_history_for_interns([c.id for c in candidates]):
        history_by_intern.setdefault(h.intern_id, []).append(h)
    return history_by_intern


def _feedback_by_intern(intern_repo: InternRepository, member_ids: list[int]) -> dict[int, list[models.MentorFeedback]]:
    feedback_by_intern: dict[int, list[models.MentorFeedback]] = {}
    for entry in intern_repo.feedback_for_interns(member_ids):
        feedback_by_intern.setdefault(entry.intern_id, []).append(entry)
    return feedback_by_intern


def _format_risk_notes(risks: list[dict]) -> str:
    if not risks:
        return "No risks identified."
    return "; ".join(f"[{r['severity'].upper()}] {r['type']}: {r['message']}" for r in risks)


@router.post("", response_model=schemas.RecommendTeamsResultOut)
def recommend_teams(request: schemas.TeamFormationRequest, db: Session = Depends(get_db)):
    """The Checkpoint 2 integration endpoint: forms teams from a candidate
    pool, then runs compatibility, skill matrix, project matching,
    workload distribution, success probability, risk analysis, and the
    Day 11 SHAP-based explanation against each one — persisting every
    result the same way each individual engine's own endpoint would.

    Errors: 404 if any `intern_ids` don't exist; 409 if fewer than 2
    candidates have embeddings, or any candidate is missing one; 422 for
    an unrecognized `algorithm`.
    """
    intern_repo = InternRepository(db)
    team_repo = TeamRepository(db)
    project_repo = ProjectRepository(db)

    candidates = _resolve_candidates(request, intern_repo)
    history_by_intern = _history_by_intern(team_repo, candidates)

    try:
        formation_result = team_formation_service.form_teams(
            candidates,
            history_by_intern=history_by_intern,
            team_size=request.team_size,
            algorithm=request.algorithm,
        )
    except team_formation_service.InsufficientCandidatesError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except team_formation_service.EmbeddingMissingError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    all_projects = project_repo.list_all()
    recommended_teams = []

    for i, formed_team in enumerate(formation_result.teams):
        members = formed_team.members

        # --- Persist the team + members (Day 7 commit + leadership apply) ---
        db_team = models.Team(name=f"Recommended Team {i + 1}")
        db.add(db_team)
        db.flush()
        for member in members:
            role = "Lead" if member.id == formed_team.suggested_leader_id else "Member"
            db.add(models.TeamMember(team_id=db_team.id, intern_id=member.id, role=role))
        db.commit()
        db.refresh(db_team)

        # --- Everything that doesn't need persisted TeamMember rows ---
        member_history = {m.id: history_by_intern.get(m.id, []) for m in members}
        feedback_by_intern = _feedback_by_intern(intern_repo, [m.id for m in members])
        result = recommend_teams_service.compute_team_recommendation(
            members, member_history, feedback_by_intern, all_projects,
        )

        # --- Persist compatibility, project assignment, success probability, risk ---
        db_team.compatibility_score = result["compatibility_score"]
        if result["project_fit"]:
            db_team.project_id = result["project_fit"]["project_id"]
        db_team.success_probability = result["success_probability"] / 100.0
        db_team.risk_notes = _format_risk_notes(result["risks"])
        team_repo.save(db_team)

        # --- Workload needs real, persisted TeamMember rows (role + team_id) ---
        workload_rows = []
        if db_team.project_id:
            project = project_repo.get_by_id(db_team.project_id)
            team_with_members = team_repo.get_by_id_with_members_and_interns(db_team.id)
            workload_rows = workload_service.distribute_workload(team_with_members.members, project)
            rows_by_intern = {r["intern_id"]: r for r in workload_rows}
            for tm in team_with_members.members:
                row = rows_by_intern.get(tm.intern_id)
                if row:
                    tm.suggested_responsibility = row["suggested_responsibility"]
                    db.add(tm)
            db.commit()

        leader = next(m for m in members if m.id == formed_team.suggested_leader_id)

        recommended_teams.append(
            schemas.RecommendedTeamOut(
                id=db_team.id,
                name=db_team.name,
                members=[
                    schemas.FormedTeamMemberOut(
                        intern_id=m.id,
                        full_name=m.full_name,
                        role="Lead" if m.id == formed_team.suggested_leader_id else "Member",
                        skill_archetype=formed_team.member_archetypes[m.id],
                    )
                    for m in members
                ],
                suggested_leader_intern_id=formed_team.suggested_leader_id,
                suggested_leader_name=leader.full_name,
                diversity_score=formed_team.diversity_score,
                skill_matrix=result["skill_matrix"],
                compatibility_score=result["compatibility_score"],
                project=schemas.ProjectFitOut(**result["project_fit"]) if result["project_fit"] else None,
                workload=[schemas.WorkloadAssignmentOut(**r) for r in workload_rows],
                success_probability=result["success_probability"],
                risks=[schemas.RiskOut(**r) for r in result["risks"]],
                overall_score=result["overall_score"],
                explanation=schemas.ExplanationOut(**result["explanation"]),
            )
        )

    return schemas.RecommendTeamsResultOut(
        algorithm=formation_result.algorithm,
        archetype_count=formation_result.archetype_count,
        teams=recommended_teams,
        unassigned_intern_ids=[i.id for i in formation_result.unassigned],
    )
