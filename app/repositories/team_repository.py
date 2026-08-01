"""Repository layer for Team / TeamHistory — introduced in Day 4, used by
the Day 4 Skill Matrix and Day 6 Compatibility engines."""
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app import models


class TeamRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, team_id: int) -> Optional[models.Team]:
        return self.db.get(models.Team, team_id)

    def get_by_id_with_members(self, team_id: int) -> Optional[models.Team]:
        return (
            self.db.query(models.Team)
            .options(joinedload(models.Team.members))
            .filter(models.Team.id == team_id)
            .first()
        )

    def get_by_id_with_members_and_interns(self, team_id: int) -> Optional[models.Team]:
        """Day 8: Workload Distribution needs each member's Intern row
        (skills, technology_stack) alongside the TeamMember role, not just
        the bare membership rows get_by_id_with_members returns."""
        return (
            self.db.query(models.Team)
            .options(joinedload(models.Team.members).joinedload(models.TeamMember.intern))
            .filter(models.Team.id == team_id)
            .first()
        )

    def list_all_with_project_and_members(self) -> list[models.Team]:
        """Day 13: Admin cross-team analytics needs every team's project
        title and member count in one query, not fetch-one-at-a-time like
        the CRUD router does."""
        return (
            self.db.query(models.Team)
            .options(joinedload(models.Team.project), joinedload(models.Team.members))
            .order_by(models.Team.id)
            .all()
        )

    def list_all_with_members_and_interns(self) -> list[models.Team]:
        """Day 16: Automatic Team Rebalancing needs every team's member
        rows *and* each member's Intern.is_available in one query, to scan
        the whole org for teams with a now-unavailable member — the same
        joinedload shape as get_by_id_with_members_and_interns, but across
        every team instead of one."""
        return (
            self.db.query(models.Team)
            .options(joinedload(models.Team.members).joinedload(models.TeamMember.intern))
            .order_by(models.Team.id)
            .all()
        )

    def assigned_intern_ids(self) -> set[int]:
        """Day 13: Resource Utilization needs the same "already on a team"
        set that InternRepository.list_available_unassigned_with_embeddings
        filters by, but as a standalone set rather than a subquery — used
        to classify every intern as assigned/unassigned regardless of
        availability or embedding status."""
        rows = self.db.query(models.TeamMember.intern_id).distinct().all()
        return {row[0] for row in rows}

    def team_history_for_interns(self, intern_ids: list[int]) -> list[models.TeamHistory]:
        if not intern_ids:
            return []
        return (
            self.db.query(models.TeamHistory)
            .filter(models.TeamHistory.intern_id.in_(intern_ids))
            .all()
        )

    def list_all_team_history(self) -> list[models.TeamHistory]:
        """Gap-fix (post-Day-20): the Engineering Knowledge Graph needs
        every WORKED_WITH edge across the whole org, not just for a known
        set of intern_ids like team_history_for_interns needs."""
        return self.db.query(models.TeamHistory).all()

    def save(self, team: models.Team, commit: bool = True) -> models.Team:
        self.db.add(team)
        if commit:
            self.db.commit()
            self.db.refresh(team)
        return team

    def delete_member(self, team_member: models.TeamMember, commit: bool = True) -> None:
        """Day 16: removes one TeamMember row — used by Automatic Team
        Rebalancing to take an unavailable member off a team before adding
        their replacement. Deliberately doesn't touch TeamHistory: no real
        outcome_rating exists for a membership that just ended mid-team,
        and fabricating one would pollute a signal Day 6/7's compatibility
        and leadership engines both treat as ground truth."""
        self.db.delete(team_member)
        if commit:
            self.db.commit()
