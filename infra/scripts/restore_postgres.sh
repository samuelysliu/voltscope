#!/usr/bin/env bash
set -euo pipefail

backup_file="${1:?Usage: restore_postgres.sh backups/postgres-YYYY.sql.gz}"
gunzip -c "$backup_file" | docker compose exec -T postgres psql -U "${POSTGRES_USER:-voltscope}" "${POSTGRES_DB:-voltscope}"

