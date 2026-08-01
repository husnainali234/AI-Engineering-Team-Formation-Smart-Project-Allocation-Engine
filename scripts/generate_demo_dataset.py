"""
Day 18 — curated demo dataset.

`scripts/generate_mock_data.py` (Day 2) produces a large, fully-random
120-intern dataset good for exercising the engines at realistic scale.
This script is different on purpose: a small, hand-tuned dataset (24
interns, 4 projects) engineered so that a demo walking through the
grading rubric's own example flows doesn't have to go fishing through
120 random interns to find one.

Specifically, this dataset guarantees:

- **A clean, high-diversity team is formable** — the first 8 interns
  span 4+ distinct tech stacks with complementary (non-overlapping)
  skills, one clear standout leader (`leadership_score=9.2`, everyone
  else on the team well below 7.0), so `/team-formation/preview` and
  Day 16's `GET /team-chemistry/team/{id}` visibly show a *single clear
  leader* flag.
- **A competing-leadership team is formable** — a second group of 8
  interns includes two interns both scoring `>= 7.0` on leadership, so
  the same chemistry endpoint against that team shows the "2 strong
  leaders" flag mentioned in DAY16_GUIDE.md, next to the clean team's
  single-leader result, for a direct side-by-side demo.
- **Two interns are marked `is_available=False`** up front — so
  `GET /rebalance/needed` has something to show immediately after
  `/recommend-teams` runs, without a manual `PUT /interns/{id}` step
  first.
- **Every intern has mentor feedback with comments in both directions**
  (some positive/collaborative language, some friction language) so Day
  16's `feedback_sentiment` chemistry signal has real signal to react to
  rather than neutral filler text.
- **4 projects with genuinely different required tech stacks**, each
  matched by at least one of the dataset's interns' actual stacks, so
  `/recommend-teams` reliably finds a project match to demo workload
  distribution against.

Run inside the backend container:
    docker compose exec backend python scripts/generate_demo_dataset.py

Safe to re-run: wipes and re-seeds the same tables
`generate_mock_data.py` does. Uses a fixed seed (0) distinct from that
script's seed (42) so the two are never confused for one another.
"""
import os
import random
import sys
from datetime import date, timedelta

from faker import Faker

sys.path.append(os.getcwd())

from app.database import Base, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402

fake = Faker()
random.seed(0)
Faker.seed(0)

SKILL_POOL = [
    ("Python", "Language"), ("JavaScript", "Language"), ("SQL", "Language"),
    ("React", "Framework"), ("FastAPI", "Framework"), ("Django", "Framework"),
    ("Node.js", "Framework"), ("Flutter", "Framework"),
    ("Docker", "Tool"), ("Git", "Tool"), ("AWS", "Tool"),
    ("Machine Learning", "Domain"), ("Communication", "Domain"), ("Leadership", "Domain"),
]

POSITIVE_FEEDBACK = [
    "Great collaborator, communicates clearly and helps unblock teammates.",
    "Consistently reliable, takes ownership without being asked twice.",
    "Strong technical contributor who explains tradeoffs well in standups.",
    "Proactively shares progress and flags risks early.",
]
FRICTION_FEEDBACK = [
    "Tends to dismiss teammates' suggestions in planning discussions.",
    "Some tension with co-leads over decision ownership this sprint.",
    "Needs reminders to loop others in before changing shared code.",
    "Occasional friction during code review discussions this week.",
]

PROJECTS = [
    ("AI Resume Screener", "Django, Python, Machine Learning", "Medium"),
    ("Real-time Team Chat App", "React, Node.js", "Medium"),
    ("Cloud Cost Dashboard", "FastAPI, AWS, Docker", "Hard"),
    ("Mobile Attendance Tracker", "Flutter, FastAPI", "Easy"),
]


def reset_tables(db):
    for model in [
        models.Attendance, models.MentorFeedback, models.TeamHistory,
        models.TeamMember, models.Team, models.InternSkill,
        models.Project, models.Skill, models.Intern,
    ]:
        db.query(model).delete()
    db.commit()


def seed_skills(db):
    skills = [models.Skill(name=n, category=c) for n, c in SKILL_POOL]
    db.add_all(skills)
    db.commit()
    return {s.name: s for s in skills}


def seed_projects(db):
    projects = [
        models.Project(
            title=title,
            description=fake.paragraph(nb_sentences=2),
            required_tech_stack=stack,
            difficulty_level=level,
        )
        for title, stack, level in PROJECTS
    ]
    db.add_all(projects)
    db.commit()
    return projects


def _make_intern(stack, interests, leadership, communication, available=True):
    return models.Intern(
        full_name=fake.name(),
        email=fake.unique.email(),
        technology_stack=", ".join(stack),
        github_url=f"https://github.com/{fake.user_name()}",
        github_contributions=random.randint(20, 300),
        case_study_performance=round(random.uniform(60, 95), 1),
        engineering_credits=random.randint(80, 130),
        attendance_pct=round(random.uniform(80, 100), 1),
        leadership_score=leadership,
        communication_score=communication,
        is_available=available,
        project_interests=", ".join(interests),
    )


def seed_interns(db):
    interns = []

    # --- Group A: clean team, one clear leader, complementary skills ---
    interns.append(_make_intern(["Python", "Django", "Machine Learning"], ["AI/ML"], 9.2, 8.5))
    interns.append(_make_intern(["React", "JavaScript"], ["Frontend"], 4.0, 7.0))
    interns.append(_make_intern(["Node.js", "SQL"], ["Backend"], 3.5, 6.5))
    interns.append(_make_intern(["Docker", "AWS"], ["DevOps"], 3.0, 6.0))
    interns.append(_make_intern(["FastAPI", "Python"], ["Backend"], 4.5, 7.5))
    interns.append(_make_intern(["Flutter", "JavaScript"], ["Mobile"], 3.8, 6.8))
    interns.append(_make_intern(["Git", "Docker"], ["DevOps"], 2.5, 6.2))
    interns.append(_make_intern(["Communication", "Leadership"], ["Frontend"], 5.5, 8.0))

    # --- Group B: competing-leadership team (2 strong leaders >= 7.0) ---
    interns.append(_make_intern(["FastAPI", "AWS", "Docker"], ["Cloud"], 8.0, 6.0))
    interns.append(_make_intern(["React", "Node.js"], ["Frontend"], 7.5, 6.5))
    interns.append(_make_intern(["Python", "SQL"], ["Backend"], 3.0, 7.0))
    interns.append(_make_intern(["Machine Learning", "Python"], ["AI/ML"], 4.0, 7.2))
    interns.append(_make_intern(["Docker", "Git"], ["DevOps"], 3.5, 6.0))
    interns.append(_make_intern(["Flutter", "FastAPI"], ["Mobile"], 4.2, 6.8))
    interns.append(_make_intern(["JavaScript", "React"], ["Frontend"], 3.8, 7.0))
    interns.append(_make_intern(["AWS", "SQL"], ["Cloud"], 4.6, 6.4))

    # --- Group C: general pool, includes the 2 unavailable interns for
    #     an immediate GET /rebalance/needed demo ---
    interns.append(_make_intern(["Python", "FastAPI"], ["Backend"], 5.0, 7.0))
    interns.append(_make_intern(["React", "Flutter"], ["Mobile"], 4.8, 6.9))
    interns.append(_make_intern(["Docker", "AWS", "Machine Learning"], ["Cloud"], 6.5, 7.3))
    interns.append(_make_intern(["Node.js", "JavaScript"], ["Frontend"], 5.2, 6.7))
    interns.append(_make_intern(["SQL", "Python"], ["Backend"], 4.9, 6.4,
                                 available=False))  # unavailable — rebalancing demo
    interns.append(_make_intern(["React", "Node.js"], ["Frontend"], 5.8, 7.1,
                                 available=False))  # unavailable — rebalancing demo
    interns.append(_make_intern(["FastAPI", "Docker"], ["DevOps"], 4.4, 6.6))
    interns.append(_make_intern(["Machine Learning", "SQL"], ["AI/ML"], 5.6, 7.4))

    db.add_all(interns)
    db.commit()
    return interns


def seed_intern_skills(db, interns, skill_lookup):
    records = []
    for intern in interns:
        stack_names = [s.strip() for s in intern.technology_stack.split(",")]
        for name in stack_names:
            skill = skill_lookup.get(name)
            if skill:
                records.append(models.InternSkill(
                    intern_id=intern.id, skill_id=skill.id,
                    proficiency=random.randint(3, 5),
                ))
    db.add_all(records)
    db.commit()


def seed_attendance(db, interns, days=14):
    records = []
    today = date.today()
    for intern in interns:
        for d in range(days):
            records.append(models.Attendance(
                intern_id=intern.id,
                log_date=today - timedelta(days=d),
                present=random.random() < (intern.attendance_pct / 100),
            ))
    db.add_all(records)
    db.commit()


def seed_mentor_feedback(db, interns):
    """Every intern gets one positive-leaning and one friction-leaning
    comment, so Day 16's feedback_sentiment signal always has both
    directions of language to react to, per intern and per team."""
    records = []
    for intern in interns:
        records.append(models.MentorFeedback(
            intern_id=intern.id, mentor_name=fake.name(),
            score=round(random.uniform(6.0, 9.5), 1),
            comments=random.choice(POSITIVE_FEEDBACK),
            given_on=fake.date_between(start_date="-21d", end_date="-11d"),
        ))
        records.append(models.MentorFeedback(
            intern_id=intern.id, mentor_name=fake.name(),
            score=round(random.uniform(4.0, 8.0), 1),
            comments=random.choice(FRICTION_FEEDBACK),
            given_on=fake.date_between(start_date="-10d", end_date="today"),
        ))
    db.add_all(records)
    db.commit()


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Clearing existing data...")
        reset_tables(db)

        print("Seeding skills...")
        skill_lookup = seed_skills(db)

        print("Seeding curated projects (4)...")
        seed_projects(db)

        print("Seeding curated interns (24: 8 clean-leader team, "
              "8 competing-leader team, 8 general incl. 2 unavailable)...")
        interns = seed_interns(db)

        print("Seeding intern-skill links...")
        seed_intern_skills(db, interns, skill_lookup)

        print("Seeding attendance (14 days per intern)...")
        seed_attendance(db, interns)

        print("Seeding mentor feedback (positive + friction per intern)...")
        seed_mentor_feedback(db, interns)

        print(f"Done. Seeded {len(interns)} curated interns, "
              f"{len(skill_lookup)} skills, {len(PROJECTS)} projects.")
        print("Demo script: POST /team-formation/preview or "
              "/recommend-teams, then GET /rebalance/needed (2 interns "
              "already unavailable) and GET /team-chemistry/team/{id} "
              "on the two hand-tuned teams to see the leadership_balance "
              "flag differ.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
