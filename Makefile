.PHONY: up dev down migrate seed seed-content-sources logs backend-test frontend-build

up:
	docker compose up -d --build

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec -e PYTHONPATH=/app backend python scripts/seed.py

seed-content-sources:
	docker compose exec -e PYTHONPATH=/app backend python scripts/seed_content_sources.py

logs:
	docker compose logs -f backend frontend nginx

backend-test:
	cd backend && pytest

frontend-build:
	cd frontend && npm run build
