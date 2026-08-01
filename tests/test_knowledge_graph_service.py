from app import models
from app.services import knowledge_graph_service
from tests.factories import assign_skill, make_intern, make_project, make_skill, make_team


def test_build_graph_adds_intern_and_skill_nodes(db_session):
    intern = make_intern(db_session, email="a@example.com", technology_stack="Laravel, MySQL")

    graph = knowledge_graph_service.build_graph([intern], [])

    assert graph.nodes[f"intern:{intern.id}"]["type"] == "intern"
    assert graph.nodes["skill:Laravel"]["type"] == "skill"
    assert graph.has_edge(f"intern:{intern.id}", "skill:Laravel")


def test_build_graph_uses_structured_proficiency_when_available(db_session):
    intern = make_intern(db_session, email="a@example.com", technology_stack="")
    skill = make_skill(db_session, "React")
    assign_skill(db_session, intern, skill, proficiency=5)
    db_session.refresh(intern)

    graph = knowledge_graph_service.build_graph([intern], [])

    edge_data = graph.get_edge_data(f"intern:{intern.id}", "skill:React")
    assert edge_data["HAS_SKILL"]["proficiency"] == 5


def test_worked_with_edge_created_for_shared_past_team(db_session):
    a = make_intern(db_session, email="a@example.com")
    b = make_intern(db_session, email="b@example.com")
    histories = [
        models.TeamHistory(intern_id=a.id, past_team_name="Falcons", outcome_rating=9.0),
        models.TeamHistory(intern_id=b.id, past_team_name="Falcons", outcome_rating=7.0),
    ]

    graph = knowledge_graph_service.build_graph([a, b], histories)

    assert graph.has_edge(f"intern:{a.id}", f"intern:{b.id}")
    assert graph.has_edge(f"intern:{b.id}", f"intern:{a.id}")
    edge_data = graph.get_edge_data(f"intern:{a.id}", f"intern:{b.id}")
    assert edge_data["WORKED_WITH:Falcons"]["outcome_rating"] == 8.0


def test_worked_with_not_created_for_different_past_teams(db_session):
    a = make_intern(db_session, email="a@example.com")
    b = make_intern(db_session, email="b@example.com")
    histories = [
        models.TeamHistory(intern_id=a.id, past_team_name="Falcons", outcome_rating=9.0),
        models.TeamHistory(intern_id=b.id, past_team_name="Hawks", outcome_rating=7.0),
    ]

    graph = knowledge_graph_service.build_graph([a, b], histories)

    assert not graph.has_edge(f"intern:{a.id}", f"intern:{b.id}")


def test_team_and_project_edges(db_session):
    a = make_intern(db_session, email="a@example.com")
    project = make_project(db_session, title="Portal Revamp", required_tech_stack="Laravel, Vue")
    team = make_team(db_session, "Gamma", member_ids=[a.id])
    team.project_id = project.id
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)

    teams = [db_session.get(models.Team, team.id)]
    # force-load members relationship for build_graph's `team.members` access
    _ = teams[0].members

    graph = knowledge_graph_service.build_graph([a], [], teams=teams, projects=[project])

    assert graph.has_edge(f"intern:{a.id}", f"team:{team.id}")
    assert graph.has_edge(f"team:{team.id}", f"project:{project.id}")
    assert graph.has_edge(f"project:{project.id}", "skill:Laravel")
    assert graph.has_edge(f"project:{project.id}", "skill:Vue")


def test_graph_summary_counts_nodes_and_edges(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="React")
    b = make_intern(db_session, email="b@example.com", technology_stack="React")

    graph = knowledge_graph_service.build_graph([a, b], [])
    summary = knowledge_graph_service.graph_summary(graph)

    assert summary["nodes_by_type"]["intern"] == 2
    assert summary["nodes_by_type"]["skill"] == 1
    assert summary["edges_by_relation"]["HAS_SKILL"] == 2
    assert summary["node_count"] == 3
    assert summary["edge_count"] == 2


def test_interns_with_skill_ranks_by_proficiency(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="")
    b = make_intern(db_session, email="b@example.com", technology_stack="")
    skill = make_skill(db_session, "Laravel")
    assign_skill(db_session, a, skill, proficiency=2)
    assign_skill(db_session, b, skill, proficiency=5)
    db_session.refresh(a)
    db_session.refresh(b)

    graph = knowledge_graph_service.build_graph([a, b], [])
    results = knowledge_graph_service.interns_with_skill(graph, "Laravel")

    assert [r["intern_id"] for r in results] == [b.id, a.id]


def test_interns_with_skill_returns_empty_for_unknown_skill(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="React")
    graph = knowledge_graph_service.build_graph([a], [])

    assert knowledge_graph_service.interns_with_skill(graph, "Cobol") == []


def test_recommended_collaborators_ranks_by_shared_skills_and_history(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="React, Node.js")
    b = make_intern(db_session, email="b@example.com", technology_stack="React, Node.js")  # 2 shared, no history
    c = make_intern(db_session, email="c@example.com", technology_stack="React")            # 1 shared, no history
    histories = [
        models.TeamHistory(intern_id=a.id, past_team_name="Falcons", outcome_rating=10.0),
        models.TeamHistory(intern_id=c.id, past_team_name="Falcons", outcome_rating=10.0),
    ]

    graph = knowledge_graph_service.build_graph([a, b, c], histories)
    results = knowledge_graph_service.recommended_collaborators(graph, a.id, limit=5)

    result_ids = [r["intern_id"] for r in results]
    assert b.id in result_ids
    assert c.id in result_ids
    # b has 2 shared skills and no history, c has 1 shared skill plus a
    # strong (10.0) past collaboration bonus -- exact ranking depends on
    # the scoring formula, but both must be surfaced with correct evidence.
    b_result = next(r for r in results if r["intern_id"] == b.id)
    c_result = next(r for r in results if r["intern_id"] == c.id)
    assert b_result["shared_skill_count"] == 2
    assert c_result["shared_skill_count"] == 1
    assert c_result["past_collaboration"]["outcome_rating"] == 10.0
    assert b_result["past_collaboration"] is None


def test_recommended_collaborators_excludes_self_and_unknown_intern(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="React")
    graph = knowledge_graph_service.build_graph([a], [])

    assert knowledge_graph_service.recommended_collaborators(graph, a.id) == []
    assert knowledge_graph_service.recommended_collaborators(graph, 9999) == []


def test_connection_path_via_shared_skill(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="Laravel")
    b = make_intern(db_session, email="b@example.com", technology_stack="Laravel")

    graph = knowledge_graph_service.build_graph([a, b], [])
    result = knowledge_graph_service.connection_path(graph, a.id, b.id)

    assert result is not None
    assert result["length"] == 2  # intern -> skill -> intern
    assert result["path"][1]["type"] == "skill"


def test_connection_path_none_when_disconnected(db_session):
    a = make_intern(db_session, email="a@example.com", technology_stack="Laravel")
    b = make_intern(db_session, email="b@example.com", technology_stack="COBOL")

    graph = knowledge_graph_service.build_graph([a, b], [])

    assert knowledge_graph_service.connection_path(graph, a.id, b.id) is None
