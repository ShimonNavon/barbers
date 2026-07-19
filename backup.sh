#!/bin/sh
# Nightly Postgres backup for barbers. Run from cron; keeps 14 days.
# TODO: push to off-box storage (Cloudflare R2) once an R2 token exists.
set -eu

BACKUP_DIR=/srv/backups/barbers
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%F_%H%M)
docker exec barbers-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$BACKUP_DIR/barbers_${STAMP}.sql.gz"

find "$BACKUP_DIR" -name 'barbers_*.sql.gz' -mtime +14 -delete
