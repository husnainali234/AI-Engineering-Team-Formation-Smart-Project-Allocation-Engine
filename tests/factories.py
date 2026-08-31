"""Small helpers for building model instances in tests without repeating
the same boilerplate in every test module."""
from app import models


def make_intern(db, **overrides) -> models.Intern:
    defaults = dict(
        full_name="Test Intern",
        email=f"intern{overrides.get('_unique', id(overrides))}@example.com",
        technology_stack="React, Node.js",
        github_contributions=10,
        case_study_performance=80.0,
        engineering_credits=90,
        attendance_pct=95.0,
        leadership_score=5.0,
        communication_score=5.0,
        is_available=True,
        project_interests="AI/ML",
    )
    overrides.pop("_unique", None)
    defaults.update(overrides)
    intern = models.Intern(**defaults)
    db.add(intern)
    db.commit()
    db.refresh(intern)
    return intern


def make_skill(db, name: str, category: str = "Framework") -> models.Skill:
    skill = models.Skill(name=name, category=category)
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


def assign_skill(db, intern: models.Intern, skill: models.Skill, proficiency: int = 3) -> models.InternSkill:
    link = models.InternSkill(intern_id=intern.id, skill_id=skill.id, proficiency=proficiency)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def make_project(db, title: str = "Test Project", required_tech_stack: str = "React") -> models.Project:
    project = models.Project(title=title, required_tech_stack=required_tech_stack)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def make_feedback(
    db, intern: models.Intern, score: float = 8.0, mentor_name: str = "Mentor", comments: str | None = None
) -> models.MentorFeedback:
    feedback = models.MentorFeedback(intern_id=intern.id, mentor_name=mentor_name, score=score, comments=comments)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def make_team(db, name: str = "Test Team", member_ids: list[int] | None = None, compatibility_score: float | None = None) -> models.Team:
    team = models.Team(name=name)
    if compatibility_score is not None:
        team.compatibility_score = compatibility_score
    db.add(team)
    db.flush()
    for intern_id in (member_ids or []):
        db.add(models.TeamMember(team_id=team.id, intern_id=intern_id))
    db.commit()
    db.refresh(team)
    return team
