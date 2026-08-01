#!/usr/bin/env bash
# Day 2 — one-command setup: brings the stack up, runs migrations, seeds mock data.
# Run from the project root: bash scripts/day2_setup.sh
set -e

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found — copying .env.example -> .env"
  cp .env.example .env
fi

echo "Building and starting containers..."
docker compose up -d --build

echo "Waiting for Postgres to be healthy..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' ai020_db 2>/dev/null)" = "healthy" ]; do
  sleep 1
done
echo "Postgres is healthy."

echo "Waiting for the backend to accept requests..."
until curl -sf http://localhost:8000/ > /dev/null 2>&1; do
  sleep 1
done

echo "Running Alembic migrations..."
docker compose exec -T backend alembic upgrade head

echo "Seeding mock data (interns, skills, projects, attendance, feedback)..."
docker compose exec -T backend python scripts/generate_mock_data.py

echo ""
echo "Day 2 setup complete."
echo "  Swagger UI:  http://localhost:8000/docs"
echo "  Seed CSV:    ./data/interns_seed.csv"
echo ""
echo "Verify row counts:"
echo "  docker compose exec db psql -U ezitech -d ezitech_ai020 -c \"SELECT count(*) FROM interns;\""
