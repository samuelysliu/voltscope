#!/usr/bin/env bash
set -euo pipefail

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="${BACKUP_DIR:-backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"

mkdir -p "${backup_dir}"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-voltscope}" "${POSTGRES_DB:-voltscope}" | gzip > "${backup_dir}/postgres-${timestamp}.sql.gz"
find "${backup_dir}" -type f -name 'postgres-*.sql.gz' -mtime "+${retention_days}" -delete
