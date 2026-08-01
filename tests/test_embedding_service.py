from app.services import embedding_service
from app.models import EMBEDDING_DIM
from tests.factories import assign_skill, make_intern, make_skill


def test_build_intern_text_includes_stack_skills_and_interests(db_session):
    intern = make_intern(db_session, technology_stack="React, Node.js", project_interests="AI/ML")
    skill = make_skill(db_session, "Docker")
    assign_skill(db_session, intern, skill, proficiency=4)

    text = embedding_service.build_intern_text(intern)

    assert "React, Node.js" in text
    assert "Docker (proficiency 4/5)" in text
    assert "AI/ML" in text


def test_build_intern_text_falls_back_when_no_profile_data(db_session):
    intern = make_intern(db_session, technology_stack=None, project_interests=None)
    text = embedding_service.build_intern_text(intern)
    assert intern.full_name in text


def test_generate_for_intern_produces_correct_dimensionality(db_session, fake_embedding_model):
    intern = make_intern(db_session, technology_stack="React")

    generated = embedding_service.generate_for_intern(intern)

    assert generated is True
    assert len(intern.skill_embedding) == EMBEDDING_DIM
    assert intern.embedding_source_hash is not None
    assert intern.embedding_updated_at is not None


def test_generate_for_intern_skips_when_cached_and_unchanged(db_session, fake_embedding_model):
    intern = make_intern(db_session, technology_stack="React")
    embedding_service.generate_for_intern(intern)
    first_vector = intern.skill_embedding

    generated_again = embedding_service.generate_for_intern(intern)

    assert generated_again is False
    assert intern.skill_embedding == first_vector


def test_generate_for_intern_recomputes_when_profile_changes(db_session, fake_embedding_model):
    intern = make_intern(db_session, technology_stack="React")
    embedding_service.generate_for_intern(intern)
    first_vector = intern.skill_embedding
    first_hash = intern.embedding_source_hash

    intern.technology_stack = "React, GraphQL"
    generated_again = embedding_service.generate_for_intern(intern)

    assert generated_again is True
    assert intern.embedding_source_hash != first_hash
    assert intern.skill_embedding != first_vector


def test_generate_for_intern_force_recomputes_even_if_unchanged(db_session, fake_embedding_model):
    intern = make_intern(db_session, technology_stack="React")
    embedding_service.generate_for_intern(intern)

    generated_again = embedding_service.generate_for_intern(intern, force=True)

    assert generated_again is True


def test_generate_for_all_reports_generated_and_cached_counts(db_session, fake_embedding_model):
    intern_a = make_intern(db_session, technology_stack="React", email="a@example.com")
    intern_b = make_intern(db_session, technology_stack="Django", email="b@example.com")

    first_summary = embedding_service.generate_for_all(db_session, [intern_a, intern_b])
    assert first_summary == {"total": 2, "generated": 2, "skipped_cached": 0, "errors": []}

    second_summary = embedding_service.generate_for_all(db_session, [intern_a, intern_b])
    assert second_summary == {"total": 2, "generated": 0, "skipped_cached": 2, "errors": []}


def test_generate_for_all_isolates_failures(db_session, fake_embedding_model, monkeypatch):
    intern_a = make_intern(db_session, technology_stack="React", email="a@example.com")
    intern_b = make_intern(db_session, technology_stack="Django", email="b@example.com")

    real_generate = embedding_service.generate_for_intern

    def _boom(intern, force=False):
        if intern.id == intern_a.id:
            raise RuntimeError("simulated model failure")
        return real_generate(intern, force=force)

    monkeypatch.setattr(embedding_service, "generate_for_intern", _boom)

    summary = embedding_service.generate_for_all(db_session, [intern_a, intern_b])

    assert summary["generated"] == 1
    assert summary["total"] == 2
    assert len(summary["errors"]) == 1
    assert str(intern_a.id) in summary["errors"][0]
