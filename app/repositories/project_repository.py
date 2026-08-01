"""
Repository layer for Project — introduced in Day 8.

Days 1-3's routers/projects.py still talks to models/db directly for plain
CRUD (same pattern as Day 1-3's other routers). This repository exists
because project_recommendation_service needs to score a team against
*every* project in one call, not fetch-one-at-a-time like the CRUD router
does.
"""
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app import models


class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, project_id: int) -> Optional[models.Project]:
        return self.db.get(models.Project, project_id)

    def list_all(self) -> list[models.Project]:
        return self.db.query(models.Project).order_by(models.Project.id).all()

    def list_all_with_teams(self) -> list[models.Project]:
        """Day 13: Admin project success rates needs every project's
        matched teams (for their success_probability/compatibility_score)
        in one query, not N+1 lookups per project."""
        return (
            self.db.query(models.Project)
            .options(joinedload(models.Project.teams))
            .order_by(models.Project.id)
            .all()
        )
