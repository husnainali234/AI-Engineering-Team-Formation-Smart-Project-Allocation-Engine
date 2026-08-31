from app.services import team_rebalancing_service
from tests.factories import make_intern, make_team


def test_teams_needing_rebalance_flags_only_teams_with_unavailable_members(db_session):
    healthy_member = make_intern(db_session, email="trs1@example.com", is_available=True)
    departing_member = make_intern(db_session, email="trs2@example.com", is_available=False)
    other_member = make_intern(db_session, email="trs3@example.com", is_available=True)

    flagged_team = make_team(
        db_session, "Flagged Team", member_ids=[healthy_member.id, departing_member.id]
    )
    healthy_team = make_team(db_session, "Healthy Team", member_ids=[other_member.id])

    # teams_needing_rebalance expects members -> intern already loaded, same
    # shape TeamRepository.list_all_with_members_and_interns returns.
    db_session.refresh(flagged_team)
    db_session.refresh(healthy_team)
    for team in (flagged_team, healthy_team):
        for member in team.members:
            _ = member.intern.is_available  # force-load relationship

    result = team_rebalancing_service.teams_needing_rebalance([flagged_team, healthy_team])

    assert len(result) == 1
    assert result[0]["team_id"] == flagged_team.id
    assert result[0]["unavailable_members"] == [
        {"intern_id": departing_member.id, "full_name": departing_member.full_name}
    ]


def test_teams_needing_rebalance_empty_when_all_members_available(db_session):
    member = make_intern(db_session, email="trs4@example.com", is_available=True)
    team = make_team(db_session, "All Good Team", member_ids=[member.id])
    db_session.refresh(team)
    for m in team.members:
        _ = m.intern.is_available

    assert team_rebalancing_service.teams_needing_rebalance([team]) == []


def test_find_replacement_picks_highest_cosine_similarity(db_session):
    departing = make_intern(db_session, email="trs5@example.com")
    departing.skill_embedding = [1.0, 0.0]

    close = make_intern(db_session, email="trs6@example.com")
    close.skill_embedding = [0.95, 0.05]
    far = make_intern(db_session, email="trs7@example.com")
    far.skill_embedding = [0.1, 0.99]

    suggestion = team_rebalancing_service.find_replacement(departing, [close, far])

    assert suggestion.replacement_intern_id == close.id
    assert suggestion.replacement_intern_name == close.full_name
    assert suggestion.similarity_score > 0.9
    assert "cosine similarity" in suggestion.reason


def test_find_replacement_returns_none_when_no_candidates_have_embeddings(db_session):
    departing = make_intern(db_session, email="trs8@example.com")
    departing.skill_embedding = [1.0, 0.0]
    no_embedding_candidate = make_intern(db_session, email="trs9@example.com")

    suggestion = team_rebalancing_service.find_replacement(departing, [no_embedding_candidate])

    assert suggestion.replacement_intern_id is None
    assert "No available" in suggestion.reason


def test_find_replacement_returns_none_when_departing_member_has_no_embedding(db_session):
    departing = make_intern(db_session, email="trs10@example.com")  # no embedding
    candidate = make_intern(db_session, email="trs11@example.com")
    candidate.skill_embedding = [1.0, 0.0]

    suggestion = team_rebalancing_service.find_replacement(departing, [candidate])

    assert suggestion.replacement_intern_id is None


def test_plan_rebalance_gives_two_departing_members_two_different_replacements(db_session):
    departing_a = make_intern(db_session, email="trs12@example.com")
    departing_a.skill_embedding = [1.0, 0.0]
    departing_b = make_intern(db_session, email="trs13@example.com")
    departing_b.skill_embedding = [0.0, 1.0]

    best_for_a = make_intern(db_session, email="trs14@example.com")
    best_for_a.skill_embedding = [0.99, 0.01]
    best_for_b = make_intern(db_session, email="trs15@example.com")
    best_for_b.skill_embedding = [0.01, 0.99]

    suggestions = team_rebalancing_service.plan_rebalance(
        [departing_a, departing_b], [best_for_a, best_for_b]
    )

    replacement_ids = [s.replacement_intern_id for s in suggestions]
    assert replacement_ids == [best_for_a.id, best_for_b.id]


def test_plan_rebalance_does_not_reuse_the_same_replacement_twice(db_session):
    departing_a = make_intern(db_session, email="trs16@example.com")
    departing_a.skill_embedding = [1.0, 0.0]
    departing_b = make_intern(db_session, email="trs17@example.com")
    departing_b.skill_embedding = [1.0, 0.0]  # same profile — would both prefer the same candidate

    only_candidate = make_intern(db_session, email="trs18@example.com")
    only_candidate.skill_embedding = [1.0, 0.0]

    suggestions = team_rebalancing_service.plan_rebalance(
        [departing_a, departing_b], [only_candidate]
    )

    assert suggestions[0].replacement_intern_id == only_candidate.id
    assert suggestions[1].replacement_intern_id is None  # pool exhausted, not reused
