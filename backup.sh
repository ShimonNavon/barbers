#!/bin/sh
# Nightly backup for barbers: Postgres dump + uploaded media. Run from cron;
# keeps 14 days. Media (member avatars, post photos, certificates) cannot be
# regenerated from the database — it needs its own archive.
# TODO: push to off-box storage (Cloudflare R2) once an R2 token exists.
set -eu

BACKUP_DIR=/srv/backups/barbers
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%F_%H%M)
docker exec barbers-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$BACKUP_DIR/barbers_${STAMP}.sql.gz"

# Stream the media volume out of the container so this works regardless of
# host-side volume paths.
docker exec barbers-backend-1 tar -cf - -C /app/media . \
  | gzip > "$BACKUP_DIR/barbers_media_${STAMP}.tar.gz"

find "$BACKUP_DIR" -name 'barbers_*.sql.gz' -mtime +14 -delete
find "$BACKUP_DIR" -name 'barbers_media_*.tar.gz' -mtime +14 -delete
