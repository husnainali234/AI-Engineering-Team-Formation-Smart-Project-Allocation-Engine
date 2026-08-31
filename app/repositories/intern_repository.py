"""
Repository layer for Intern — introduced in Day 4.

Days 1-3 kept DB access directly in the routers (fine for plain CRUD). From
Day 4 onward, the embedding pipeline, skill matrix, matching engine, and
compatibility engine all need overlapping, slightly more involved queries
(e.g. "interns with a usable embedding", "interns on this team"), so those
are centralized here instead of being copy-pasted across four new service
modules. Existing Day 1-3 routers are untouched and keep talking to
`models`/`db` directly — this repository is additive, not a replacement.
"""
from typing import Iterable, Optional

from sqlalchemy.orm import Session, joinedload

from app import models


class InternRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, intern_id: int) -> Optional[models.Intern]:
        return self.db.get(models.Intern, intern_id)

    def get_by_id_with_skills(self, intern_id: int) -> Optional[models.Intern]:
        return (
            self.db.query(models.Intern)
            .options(joinedload(models.Intern.skills).joinedload(models.InternSkill.skill))
            .filter(models.Intern.id == intern_id)
            .first()
        )

    def list_all(self) -> list[models.Intern]:
        return self.db.query(models.Intern).order_by(models.Intern.id).all()

    def list_all_with_skills(self) -> list[models.Intern]:
        return (
            self.db.query(models.Intern)
            .options(joinedload(models.Intern.skills).joinedload(models.InternSkill.skill))
            .order_by(models.Intern.id)
            .all()
        )

    def list_by_ids(self, intern_ids: Iterable[int]) -> list[models.Intern]:
        ids = list(intern_ids)
        if not ids:
            return []
        return (
            self.db.query(models.Intern)
            .options(joinedload(models.Intern.skills).joinedload(models.InternSkill.skill))
            .filter(models.Intern.id.in_(ids))
            .all()
        )

    def list_with_embeddings(self, exclude_ids: Iterable[int] = ()) -> list[models.Intern]:
        """Interns that have a usable (non-null) skill_embedding — the pool
        the matching engine can actually compare against."""
        query = self.db.query(models.Intern).filter(models.Intern.skill_embedding.isnot(None))
        exclude = set(exclude_ids)
        if exclude:
            query = query.filter(models.Intern.id.notin_(exclude))
        return query.order_by(models.Intern.id).all()

    def list_available_unassigned_with_embeddings(self) -> list[models.Intern]:
        """Interns with a usable embedding, marked available, AND not
        already on a team — the default candidate pool for Day 7's Team
        Formation Engine. Unlike list_with_embeddings (Day 6's 1-to-1
        matching, which doesn't care if a candidate is already teamed),
        team *formation* actually creates commitments, so silently
        double-booking someone already on another team would be a real
        bug, not just a stale suggestion."""
        already_teamed = self.db.query(models.TeamMember.intern_id).distinct()
        return (
            self.db.query(models.Intern)
            .filter(models.Intern.skill_embedding.isnot(None))
            .filter(models.Intern.is_available.is_(True))
            .filter(models.Intern.id.notin_(already_teamed))
            .order_by(models.Intern.id)
            .all()
        )

    def list_by_team(self, team_id: int) -> list[models.Intern]:
        return (
            self.db.query(models.Intern)
            .join(models.TeamMember, models.TeamMember.intern_id == models.Intern.id)
            .options(joinedload(models.Intern.skills).joinedload(models.InternSkill.skill))
            .filter(models.TeamMember.team_id == team_id)
            .order_by(models.Intern.id)
            .all()
        )

    def feedback_for_interns(self, intern_ids: Iterable[int]) -> list[models.MentorFeedback]:
        """Day 9: Success Probability needs each team member's mentor
        feedback history to compute the team's average feedback signal."""
        ids = list(intern_ids)
        if not ids:
            return []
        return (
            self.db.query(models.MentorFeedback)
            .filter(models.MentorFeedback.intern_id.in_(ids))
            .all()
        )

    def get_by_id_with_team_context(self, intern_id: int) -> Optional[models.Intern]:
        """Day 14: Student Dashboard needs this intern's skills (for
        strengths/top-skills), their team membership row (role,
        suggested_responsibility), that team's project, and every
        teammate's name — all in one query rather than four."""
        return (
            self.db.query(models.Intern)
            .options(
                joinedload(models.Intern.skills).joinedload(models.InternSkill.skill),
                joinedload(models.Intern.team_memberships)
                .joinedload(models.TeamMember.team)
                .joinedload(models.Team.project),
                joinedload(models.Intern.team_memberships)
                .joinedload(models.TeamMember.team)
                .joinedload(models.Team.members)
                .joinedload(models.TeamMember.intern),
            )
            .filter(models.Intern.id == intern_id)
            .first()
        )

    def save(self, intern: models.Intern, commit: bool = True) -> models.Intern:
        self.db.add(intern)
        if commit:
            self.db.commit()
            self.db.refresh(intern)
        return intern
