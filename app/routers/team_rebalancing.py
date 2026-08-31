"""Day 16 — Bonus Feature (Engineer A): /rebalance endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services import leadership_service, recommend_teams_service, team_rebalancing_service, workload_service

router = APIRouter(prefix="/rebalance", tags=["rebalance"])


def _format_risk_notes(risks: list[dict]) -> str:
    if not risks:
        return "No risks identified."
    return "; ".join(f"[{r['severity'].upper()}] {r['type']}: {r['message']}" for r in risks)


@router.get("/needed", response_model=schemas.RebalanceNeededListOut)
def rebalance_needed(db: Session = Depends(get_db)):
    """Every team with at least one member whose Intern.is_available is
    False — the "member becomes unavailable" trigger surfaced as a
    reviewable list rather than acted on automatically (see
    DAY16_GUIDE.md for why this isn't a silent side-effect of
    PATCH /interns/{id})."""
    teams = TeamRepository(db).list_all_with_members_and_interns()
    flagged = team_rebalancing_service.teams_needing_rebalance(teams)
    return schemas.RebalanceNeededListOut(
        teams=[
            schemas.RebalanceNeededEntryOut(
                team_id=t["team_id"],
                team_name=t["team_name"],
                unavailable_members=[schemas.UnavailableMemberOut(**m) for m in t["unavailable_members"]],
            )
            for t in flagged
        ]
    )


@router.post("/team/{team_id}", response_model=schemas.TeamRebalanceOut)
def rebalance_team(team_id: int, db: Session = Depends(get_db)):
    """Swaps every currently-unavailable member on this team for the
    best-fit available/unassigned/embedded candidate (highest skill-
    embedding cosine similarity to the departing member — see
    team_rebalancing_service.find_replacement), re-suggests a leader if
    the departing member held that role, then reruns the same scoring
    pipeline POST /recommend-teams uses (compatibility, project fit,
    success probability, risk, workload) against the new membership,
    persisting the result the same way /recommend-teams does.

    A departing member with no available replacement is left on the team
    (removing them without a replacement would just trade one problem —
    "unavailable member still listed" — for a worse one — "team silently
    down a person") and the team stays flagged by GET /rebalance/needed
    until a replacement exists.

    404 if the team doesn't exist. 409 if the team currently has no
    unavailable members — nothing to rebalance."""
    team_repo = TeamRepository(db)
    intern_repo = InternRepository(db)
    project_repo = ProjectRepository(db)

    team = team_repo.get_by_id_with_members_and_interns(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    unavailable_tms = [tm for tm in team.members if tm.intern and not tm.intern.is_available]
    if not unavailable_tms:
        raise HTTPException(status_code=409, detail="This team has no unavailable members to rebalance")

    departing_interns = [tm.intern for tm in unavailable_tms]
    candidate_pool = intern_repo.list_available_unassigned_with_embeddings()
    suggestions = team_rebalancing_service.plan_rebalance(departing_interns, candidate_pool)

    swap_outputs = []
    had_lead_departure = False
    for tm, suggestion in zip(unavailable_tms, suggestions):
        if tm.role == "Lead" and suggestion.replacement_intern_id is not None:
            had_lead_departure = True
        if suggestion.replacement_intern_id is not None:
            team_repo.delete_member(tm, commit=False)
            db.add(models.TeamMember(team_id=team.id, intern_id=suggestion.replacement_intern_id, role="Member"))
        swap_outputs.append(
            schemas.RebalanceSwapOut(
                departing_intern_id=suggestion.departing_intern_id,
                departing_intern_name=suggestion.departing_intern_name,
                replacement_intern_id=suggestion.replacement_intern_id,
                replacement_intern_name=suggestion.replacement_intern_name,
                similarity_score=suggestion.similarity_score,
                reason=suggestion.reason,
            )
        )
    db.commit()

    team = team_repo.get_by_id_with_members_and_interns(team_id)
    final_members = [tm.intern for tm in team.members]

    if had_lead_departure and final_members:
        history_by_intern: dict[int, list] = {}
        for h in team_repo.team_history_for_interns([m.id for m in final_members]):
            history_by_intern.setdefault(h.intern_id, []).append(h)
        new_leader = leadership_service.suggest_leader(final_members, history_by_intern)
        for tm in team.members:
            tm.role = "Lead" if tm.intern_id == new_leader["intern_id"] else "Member"
            db.add(tm)
        db.commit()
        team = team_repo.get_by_id_with_members_and_interns(team_id)
        final_members = [tm.intern for tm in team.members]

    # --- Rescore exactly the way /recommend-teams scores a freshly-formed team ---
    history_by_intern = {}
    for h in team_repo.team_history_for_interns([m.id for m in final_members]):
        history_by_intern.setdefault(h.intern_id, []).append(h)
    feedback_by_intern: dict[int, list] = {}
    for entry in intern_repo.feedback_for_interns([m.id for m in final_members]):
        feedback_by_intern.setdefault(entry.intern_id, []).append(entry)
    all_projects = project_repo.list_all()

    result = recommend_teams_service.compute_team_recommendation(
        final_members, history_by_intern, feedback_by_intern, all_projects,
    )

    team.compatibility_score = result["compatibility_score"]
    if result["project_fit"]:
        team.project_id = result["project_fit"]["project_id"]
    team.success_probability = result["success_probability"] / 100.0
    team.risk_notes = _format_risk_notes(result["risks"])
    team_repo.save(team)

    workload_rows = []
    if team.project_id:
        project = project_repo.get_by_id(team.project_id)
        team_with_members = team_repo.get_by_id_with_members_and_interns(team.id)
        workload_rows = workload_service.distribute_workload(team_with_members.members, project)
        rows_by_intern = {r["intern_id"]: r for r in workload_rows}
        for tm in team_with_members.members:
            row = rows_by_intern.get(tm.intern_id)
            if row:
                tm.suggested_responsibility = row["suggested_responsibility"]
                db.add(tm)
        db.commit()

    team = team_repo.get_by_id_with_members_and_interns(team_id)

    return schemas.TeamRebalanceOut(
        team_id=team.id,
        team_name=team.name,
        swaps=swap_outputs,
        members=[
            schemas.RebalancedTeamMemberOut(intern_id=tm.intern_id, full_name=tm.intern.full_name, role=tm.role)
            for tm in team.members
        ],
        compatibility_score=team.compatibility_score,
        project=schemas.ProjectFitOut(**result["project_fit"]) if result["project_fit"] else None,
        success_probability=result["success_probability"],
        risks=[schemas.RiskOut(**r) for r in result["risks"]],
        workload=[schemas.WorkloadAssignmentOut(**r) for r in workload_rows],
    )
