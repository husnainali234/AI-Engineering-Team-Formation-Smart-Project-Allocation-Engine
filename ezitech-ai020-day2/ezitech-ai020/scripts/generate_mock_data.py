"""
Day 2 — synthetic dataset generator.

Simulates an export from the Ezitech Internship Portal: 100-150 interns with
skills, GitHub activity, attendance, mentor feedback, and project interests,
plus a small pool of skills/projects and a bit of team history so every
signal the Day 1 ERD defines actually has data behind it.

Run inside the backend container (has the DB reachable at host "db"):
    docker compose exec backend python scripts/generate_mock_data.py

Safe to re-run: it wipes and re-seeds every table it touches.
"""
import csv
import os
import random
import sys
from datetime import timedelta, date

from faker import Faker

# Run from the project root (docker compose exec backend python scripts/...
# does this automatically). Add cwd to sys.path so "app" is importable
# regardless of how the script is invoked, matching alembic/env.py.
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine, Base  # noqa: E402
from app import models  # noqa: E402

fake = Faker()
random.seed(42)
Faker.seed(42)

N_INTERNS = 120
N_PROJECTS = 15

TECH_STACKS = [
    "React", "Node.js", "Laravel", "Django", "FastAPI", "Flutter",
    "React Native", "Vue.js", "Spring Boot", "MERN", "AI/ML", "DevOps",
    "MySQL", "MongoDB", "PostgreSQL",
]

SKILL_POOL = [
    ("Python", "Language"), ("JavaScript", "Language"), ("PHP", "Language"),
    ("Java", "Language"), ("SQL", "Language"),
    ("React", "Framework"), ("Node.js", "Framework"), ("Laravel", "Framework"),
    ("Django", "Framework"), ("FastAPI", "Framework"), ("Flutter", "Framework"),
    ("Docker", "Tool"), ("Git", "Tool"), ("AWS", "Tool"), ("Figma", "Tool"),
    ("Machine Learning", "Domain"), ("Communication", "Domain"), ("Leadership", "Domain"),
]

PROJECT_TITLES = [
    "Inventory Management System", "AI Resume Screener", "E-Commerce Platform",
    "Hospital Management App", "Real-time Chat App", "Learning Management System",
    "Expense Tracker", "Food Delivery App", "AI Chatbot Assistant",
    "Property Listing Portal", "Fitness Tracking App", "Event Booking System",
    "CRM Dashboard", "Job Portal", "Recipe Sharing App",
]

DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]


def reset_tables(db):
    """Delete existing rows (children first) so the script is re-runnable."""
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
    return skills


def seed_projects(db):
    projects = []
    for title in PROJECT_TITLES[:N_PROJECTS]:
        p = models.Project(
            title=title,
            description=fake.paragraph(nb_sentences=3),
            required_tech_stack=", ".join(random.sample(TECH_STACKS, k=random.randint(2, 3))),
            difficulty_level=random.choice(DIFFICULTY_LEVELS),
        )
        projects.append(p)
    db.add_all(projects)
    db.commit()
    return projects


def seed_interns(db, n=N_INTERNS):
    interns = []
    for _ in range(n):
        stack = random.sample(TECH_STACKS, k=random.randint(2, 4))
        interests = random.sample(TECH_STACKS, k=random.randint(1, 3))
        intern = models.Intern(
            full_name=fake.name(),
            email=fake.unique.email(),
            technology_stack=", ".join(stack),
            github_url=f"https://github.com/{fake.user_name()}",
            github_contributions=random.randint(5, 400),
            case_study_performance=round(random.uniform(40, 100), 1),
            engineering_credits=random.randint(60, 140),
            attendance_pct=round(random.uniform(60, 100), 1),
            leadership_score=round(random.uniform(1, 10), 1),
            communication_score=round(random.uniform(1, 10), 1),
            is_available=random.random() > 0.1,
            project_interests=", ".join(interests),
        )
        interns.append(intern)
    db.add_all(interns)
    db.commit()
    return interns


def seed_intern_skills(db, interns, skills):
    records = []
    for intern in interns:
        chosen = random.sample(skills, k=random.randint(4, 8))
        for skill in chosen:
            records.append(models.InternSkill(
                intern_id=intern.id,
                skill_id=skill.id,
                proficiency=random.randint(1, 5),
            ))
    db.add_all(records)
    db.commit()


def seed_attendance(db, interns, days=30):
    records = []
    today = date.today()
    for intern in interns:
        for d in range(days):
            log_date = today - timedelta(days=d)
            records.append(models.Attendance(
                intern_id=intern.id,
                log_date=log_date,
                present=random.random() < (intern.attendance_pct / 100),
            ))
    db.add_all(records)
    db.commit()


def seed_mentor_feedback(db, interns, per_intern=2):
    records = []
    for intern in interns:
        for _ in range(per_intern):
            records.append(models.MentorFeedback(
                intern_id=intern.id,
                mentor_name=fake.name(),
                score=round(random.uniform(2.5, 10.0), 1),
                comments=fake.sentence(nb_words=12),
                given_on=fake.date_between(start_date="-60d", end_date="today"),
            ))
    db.add_all(records)
    db.commit()


def seed_team_history(db, interns, pct_with_history=0.5):
    """Simulate some interns having been on a team in a previous batch."""
    records = []
    sample = random.sample(interns, k=int(len(interns) * pct_with_history))
    for intern in sample:
        records.append(models.TeamHistory(
            intern_id=intern.id,
            past_team_name=f"{fake.word().capitalize()} Squad",
            past_project_title=random.choice(PROJECT_TITLES),
            outcome_rating=round(random.uniform(3, 10), 1),
        ))
    db.add_all(records)
    db.commit()


def export_csv(interns):
    path = "data/interns_seed.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "full_name", "email", "technology_stack", "github_contributions",
            "case_study_performance", "attendance_pct", "leadership_score",
            "communication_score", "is_available", "project_interests",
        ])
        for i in interns:
            writer.writerow([
                i.id, i.full_name, i.email, i.technology_stack, i.github_contributions,
                i.case_study_performance, i.attendance_pct, i.leadership_score,
                i.communication_score, i.is_available, i.project_interests,
            ])
    return path


def main():
    # Belt-and-braces: make sure tables exist even if alembic hasn't been run yet.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("Clearing existing mock data...")
        reset_tables(db)

        print("Seeding skills...")
        skills = seed_skills(db)

        print("Seeding projects...")
        seed_projects(db)

        print(f"Seeding {N_INTERNS} interns...")
        interns = seed_interns(db)

        print("Seeding intern-skill links...")
        seed_intern_skills(db, interns, skills)

        print("Seeding attendance (30 days per intern)...")
        seed_attendance(db, interns)

        print("Seeding mentor feedback...")
        seed_mentor_feedback(db, interns)

        print("Seeding team history...")
        seed_team_history(db, interns)

        print("Exporting CSV...")
        path = export_csv(interns)

        print(f"Done. Seeded {len(interns)} interns, {len(skills)} skills, "
              f"{N_PROJECTS} projects. CSV written to {path}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
