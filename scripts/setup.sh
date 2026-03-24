#!/usr/bin/env bash
set -e

echo "==> MenuGen local setup"

# 1. Check .env
if [ ! -f .env ]; then
  echo "--> Copying .env.example to .env"
  cp .env.example .env
  echo "    Edit .env and fill in the required values, then re-run this script."
  exit 1
fi

# 2. Build images
echo "--> Building Docker images"
docker compose build

# 3. Start DB and Redis first
echo "--> Starting DB and Redis"
docker compose up -d db redis

# 4. Wait for DB
echo "--> Waiting for PostgreSQL..."
until docker compose exec db pg_isready -U "$(grep DB_USER .env | cut -d= -f2)" > /dev/null 2>&1; do
  sleep 1
done
echo "    PostgreSQL is ready."

# 5. Run migrations
echo "--> Running migrations"
docker compose run --rm backend python manage.py migrate

# 6. Start all services
echo "--> Starting all services"
docker compose up -d

echo ""
echo "==> Done! Services running:"
echo "    API:     http://localhost:8000"
echo "    Swagger: http://localhost:8000/api/v1/docs/"
echo "    Admin:   http://localhost:8000/admin/"
echo ""
echo "    Run 'make createsuperuser' to create an admin account."
