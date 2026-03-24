.PHONY: help up down build logs shell migrate makemigrations test lint format

help:
	@echo "MenuGen dev commands:"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make build        - Rebuild images"
	@echo "  make logs         - Tail logs"
	@echo "  make shell        - Django shell"
	@echo "  make migrate      - Run migrations"
	@echo "  make makemigrations - Make migrations"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters"
	@echo "  make format       - Auto-format code"
	@echo "  make createsuperuser - Create admin user"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f backend

shell:
	docker compose exec backend python manage.py shell

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

test:
	docker compose exec backend pytest

lint:
	docker compose exec backend flake8 .
	docker compose exec backend black --check .
	docker compose exec backend isort --check-only .

format:
	docker compose exec backend black .
	docker compose exec backend isort .

createsuperuser:
	docker compose exec backend python manage.py createsuperuser
