"""
Gap-fix (post-Day-20 QA pass) — Engineering Knowledge Graph.

The case study PDF lists "Engineering Knowledge Graph" as a required AI
Architecture component (Section: AI Architecture Requirements), independent
of the "suggested technologies" table further down that names Neo4j. The
Execution Guide's Day-1 tech-choice table already anticipated this and
picked NetworkX in-process specifically to avoid standing up a separate
graph database server ("saves 1-2 days of setup... upgrade to Neo4j only if
time remains") — but the engine itself was never actually built in Days
1-20. This module builds it, using exactly that NetworkX-in-process
approach, from data the app already has (Intern, Skill, InternSkill, Team,
TeamMember, TeamHistory, Project) — no new tables, no new migration.

Graph shape (a MultiDiGraph so parallel edges of different kinds between
the same two nodes are all preserved):

    intern --HAS_SKILL(proficiency)--> skill
    intern --WORKED_WITH(outcome_rating, past_team_name)--> intern   (undirected in effect: added both ways)
    intern --MEMBER_OF(role)--> team
    team   --ASSIGNED_TO--> project
    project--REQUIRES--> skill

Node ids are namespaced strings ("intern:12", "skill:React", "team:3",
"project:5") so the four entity types can share one graph without id
collisions.

This intentionally stays a *read-model* built fresh from a DB query on each
call (build_graph is cheap — a few thousand interns/skills is a small graph
for NetworkX) rather than a persisted, incrementally-updated structure.
That matches the "in-process library" scope the execution guide chose over
a standalone graph server, and avoids a second source of truth that could
drift from the relational data.
"""
import networkx as nx

from app import models
from app.services.skill_utils import intern_proficiency_map, intern_skill_names


def _intern_node(intern_id: int) -> str:
    return f"intern:{intern_id}"


def _skill_node(name: str) -> str:
    return f"skill:{name}"


def _team_node(team_id: int) -> str:
    return f"team:{team_id}"


def _project_node(project_id: int) -> str:
    return f"project:{project_id}"


def build_graph(
    interns: list[models.Intern],
    team_histories: list[models.TeamHistory],
    teams: list[models.Team] | None = None,
    projects: list[models.Project] | None = None,
) -> nx.MultiDiGraph:
    """Builds the full Engineering Knowledge Graph from already-loaded
    ORM rows (callers pull these via the repository layer — see the
    knowledge_graph router — so this function itself never touches the
    DB directly, matching every other *_service.py module's shape)."""
    graph = nx.MultiDiGraph()

    # --- intern <-> skill -------------------------------------------------
    for intern in interns:
        graph.add_node(_intern_node(intern.id), type="intern", name=intern.full_name)
        proficiency_map = intern_proficiency_map(intern)
        for skill_name in intern_skill_names(intern):
            graph.add_node(_skill_node(skill_name), type="skill", name=skill_name)
            graph.add_edge(
                _intern_node(intern.id),
                _skill_node(skill_name),
                key="HAS_SKILL",
                relation="HAS_SKILL",
                # technology_stack tokens carry no proficiency rating (see
                # skill_utils' module docstring) — default to a neutral 3/5
                # rather than treating "no rating on file" as "no skill".
                proficiency=proficiency_map.get(skill_name, 3),
            )

    # --- intern <-> intern (shared past team, from TeamHistory) -----------
    # Two interns who each have a TeamHistory row naming the same
    # past_team_name were on that team together — the edge weight is the
    # average of their two outcome_rating values (how well that team did),
    # so "worked together, went well" and "worked together, went poorly"
    # are distinguishable rather than collapsed into one WORKED_WITH edge.
    by_past_team: dict[str, list[models.TeamHistory]] = {}
    for history in team_histories:
        if history.past_team_name:
            by_past_team.setdefault(history.past_team_name, []).append(history)

    for past_team_name, entries in by_past_team.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                a, b = entries[i], entries[j]
                if a.intern_id == b.intern_id:
                    continue
                ratings = [r.outcome_rating for r in (a, b) if r.outcome_rating is not None]
                avg_rating = sum(ratings) / len(ratings) if ratings else None
                for src, dst in ((a.intern_id, b.intern_id), (b.intern_id, a.intern_id)):
                    graph.add_edge(
                        _intern_node(src),
                        _intern_node(dst),
                        key=f"WORKED_WITH:{past_team_name}",
                        relation="WORKED_WITH",
                        past_team_name=past_team_name,
                        outcome_rating=avg_rating,
                    )

    # --- intern <-> team, team <-> project, project <-> skill -------------
    for team in teams or []:
        graph.add_node(_team_node(team.id), type="team", name=team.name)
        for member in team.members or []:
            graph.add_node(_intern_node(member.intern_id), type="intern")
            graph.add_edge(
                _intern_node(member.intern_id),
                _team_node(team.id),
                key="MEMBER_OF",
                relation="MEMBER_OF",
                role=member.role,
            )
        if team.project_id:
            graph.add_edge(
                _team_node(team.id),
                _project_node(team.project_id),
                key="ASSIGNED_TO",
                relation="ASSIGNED_TO",
            )

    for project in projects or []:
        graph.add_node(_project_node(project.id), type="project", name=project.title)
        for token in (project.required_tech_stack or "").split(","):
            token = token.strip()
            if token:
                graph.add_node(_skill_node(token), type="skill", name=token)
                graph.add_edge(
                    _project_node(project.id),
                    _skill_node(token),
                    key="REQUIRES",
                    relation="REQUIRES",
                )

    return graph


def graph_summary(graph: nx.MultiDiGraph) -> dict:
    """Node/edge counts by type — the Explainability-friendly "what did we
    actually build" view, and a cheap smoke test that the graph isn't
    accidentally empty."""
    node_counts: dict[str, int] = {}
    for _, attrs in graph.nodes(data=True):
        node_type = attrs.get("type", "unknown")
        node_counts[node_type] = node_counts.get(node_type, 0) + 1

    edge_counts: dict[str, int] = {}
    for _, _, attrs in graph.edges(data=True):
        relation = attrs.get("relation", "unknown")
        edge_counts[relation] = edge_counts.get(relation, 0) + 1

    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "nodes_by_type": node_counts,
        "edges_by_relation": edge_counts,
    }


def interns_with_skill(graph: nx.MultiDiGraph, skill_name: str) -> list[dict]:
    """Every intern connected to this skill node via HAS_SKILL, ranked by
    proficiency desc — answers the case study's example question directly
    ("Which Laravel developers should work together?" starts with "which
    interns have Laravel at all", which is this call)."""
    skill_node = _skill_node(skill_name)
    if skill_node not in graph:
        return []

    results = []
    for predecessor in graph.predecessors(skill_node):
        if graph.nodes[predecessor].get("type") != "intern":
            continue
        for edge_data in graph.get_edge_data(predecessor, skill_node).values():
            if edge_data.get("relation") == "HAS_SKILL":
                results.append(
                    {
                        "intern_id": int(predecessor.split(":", 1)[1]),
                        "proficiency": edge_data.get("proficiency", 0),
                    }
                )
                break

    results.sort(key=lambda r: r["proficiency"], reverse=True)
    return results


def recommended_collaborators(graph: nx.MultiDiGraph, intern_id: int, limit: int = 5) -> list[dict]:
    """For one intern, ranks every other intern by (a) how many skills they
    share (graph co-occurrence via a shared skill node — two hops:
    intern -> skill <- other intern) and (b) whether a WORKED_WITH edge
    already exists between them, and if so how that past team scored. This
    is the graph-native version of "who should this person work with next",
    distinct from Day 6's embedding-cosine-similarity matching engine —
    here the reasoning is inspectable hop-by-hop rather than a similarity
    score over an opaque embedding, which is exactly what a knowledge graph
    is for."""
    source = _intern_node(intern_id)
    if source not in graph:
        return []

    shared_skill_counts: dict[str, set[str]] = {}
    for _, skill_node, edge_data in graph.out_edges(source, data=True):
        if edge_data.get("relation") != "HAS_SKILL":
            continue
        for candidate in graph.predecessors(skill_node):
            if candidate == source or graph.nodes[candidate].get("type") != "intern":
                continue
            shared_skill_counts.setdefault(candidate, set()).add(graph.nodes[skill_node]["name"])

    past_collaboration: dict[str, dict] = {}
    for _, other, edge_data in graph.out_edges(source, data=True):
        if edge_data.get("relation") == "WORKED_WITH":
            past_collaboration[other] = {
                "past_team_name": edge_data.get("past_team_name"),
                "outcome_rating": edge_data.get("outcome_rating"),
            }

    candidates = []
    for other_node, shared_skills in shared_skill_counts.items():
        past = past_collaboration.get(other_node)
        score = len(shared_skills) + (0.5 * (past["outcome_rating"] or 0) / 10.0 if past else 0.0)
        candidates.append(
            {
                "intern_id": int(other_node.split(":", 1)[1]),
                "shared_skills": sorted(shared_skills),
                "shared_skill_count": len(shared_skills),
                "past_collaboration": past,
                "score": round(score, 4),
            }
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:limit]


def connection_path(graph: nx.MultiDiGraph, intern_a_id: int, intern_b_id: int) -> dict | None:
    """Shortest path connecting two interns through the graph — through a
    shared skill, a shared team, or a direct WORKED_WITH edge, whichever is
    fewest hops. Returns None if they're in different connected components
    (no path exists on the current data). Explains the path as a sequence
    of human-readable hops rather than raw node ids, since "why are these
    two connected" is the whole point of exposing this endpoint."""
    source, target = _intern_node(intern_a_id), _intern_node(intern_b_id)
    if source not in graph or target not in graph:
        return None

    undirected = graph.to_undirected(as_view=True)
    try:
        node_path = nx.shortest_path(undirected, source, target)
    except nx.NetworkXNoPath:
        return None

    hops = []
    for node_id in node_path:
        node_type = graph.nodes[node_id].get("type", "unknown")
        name = graph.nodes[node_id].get("name", node_id.split(":", 1)[1])
        hops.append({"node": node_id, "type": node_type, "name": name})

    return {"length": len(node_path) - 1, "path": hops}
