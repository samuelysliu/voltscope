#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python scripts/seed.py
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python scripts/seed_content_sources.py
