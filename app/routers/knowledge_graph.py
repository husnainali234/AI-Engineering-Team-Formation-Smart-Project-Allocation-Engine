"""
Gap-fix (post-Day-20 QA pass) — /knowledge-graph endpoints.

Exposes app/services/knowledge_graph_service.py's in-process NetworkX
Engineering Knowledge Graph. See that module's docstring for why this
exists and why NetworkX-in-process rather than a standalone Neo4j server.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas
from app.repositories.intern_repository import InternRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.team_repository import TeamRepository
from app.services import knowledge_graph_service

router = APIRouter(prefix="/knowledge-graph", tags=["knowledge-graph"])


def _build_full_graph(db: Session):
    interns = InternRepository(db).list_all_with_skills()
    team_histories = TeamRepository(db).list_all_team_history()
    teams = TeamRepository(db).list_all_with_project_and_members()
    projects = ProjectRepository(db).list_all()
    return knowledge_graph_service.build_graph(interns, team_histories, teams, projects)


@router.get("/summary", response_model=schemas.KnowledgeGraphSummaryOut)
def summary(db: Session = Depends(get_db)):
    """Node/edge counts by type — a quick sanity check on graph size and
    the shape of what's actually connected right now."""
    graph = _build_full_graph(db)
    result = knowledge_graph_service.graph_summary(graph)
    return schemas.KnowledgeGraphSummaryOut(**result)


@router.get("/skill/{skill_name}/interns", response_model=list[schemas.SkillGraphInternOut])
def interns_with_skill(skill_name: str, db: Session = Depends(get_db)):
    """Every intern with this skill, ranked by proficiency — e.g.
    GET /knowledge-graph/skill/Laravel/interns directly answers the case
    study's example question ("Which Laravel developers should work
    together?") at the first step: who are the candidates at all."""
    graph = _build_full_graph(db)
    return [
        schemas.SkillGraphInternOut(**entry)
        for entry in knowledge_graph_service.interns_with_skill(graph, skill_name)
    ]


@router.get(
    "/intern/{intern_id}/recommended-collaborators",
    response_model=list[schemas.RecommendedCollaboratorOut],
)
def recommended_collaborators(intern_id: int, limit: int = 5, db: Session = Depends(get_db)):
    """Graph-native collaborator suggestions for one intern: ranked by
    shared skills (two-hop: intern -> skill <- other intern) with a bonus
    when a past WORKED_WITH edge already exists and scored well. Every
    result carries the actual shared skills and past-team evidence it was
    scored from, not an opaque similarity number."""
    intern = InternRepository(db).get_by_id(intern_id)
    if not intern:
        raise HTTPException(status_code=404, detail="Intern not found")

    graph = _build_full_graph(db)
    return [
        schemas.RecommendedCollaboratorOut(**entry)
        for entry in knowledge_graph_service.recommended_collaborators(graph, intern_id, limit=limit)
    ]


@router.get("/path", response_model=schemas.KnowledgeGraphPathOut)
def connection_path(intern_a_id: int, intern_b_id: int, db: Session = Depends(get_db)):
    """Shortest explainable path connecting two interns through the graph
    (shared skill, shared team, or a direct past collaboration) — 404s if
    either intern doesn't exist, 200 with found=false if they exist but
    are in disconnected parts of the graph (e.g. no shared skills, teams,
    or history yet)."""
    intern_repo = InternRepository(db)
    if not intern_repo.get_by_id(intern_a_id) or not intern_repo.get_by_id(intern_b_id):
        raise HTTPException(status_code=404, detail="One or both interns not found")

    graph = _build_full_graph(db)
    result = knowledge_graph_service.connection_path(graph, intern_a_id, intern_b_id)
    if result is None:
        return schemas.KnowledgeGraphPathOut(found=False, length=None, path=[])
    return schemas.KnowledgeGraphPathOut(found=True, length=result["length"], path=result["path"])
