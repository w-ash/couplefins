#!/usr/bin/env bash
# Dump the Neon production database to a local timestamped file.
# Requires the couplefins-postgres Docker container (has pg_dump 18).
#
# Usage:
#   ./scripts/backup-neon.sh
#
# Backups go to backups/ with 7-day retention (older files are pruned).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=7

# Non-pooled endpoint (pg_dump doesn't work through the pooler)
NEON_HOST="ep-round-wildflower-akeu4b5j.c-3.us-west-2.aws.neon.tech"
NEON_USER="neondb_owner"
NEON_DB="neondb"

# Read password from .env to avoid hardcoding
NEON_PASSWORD=$(grep '^DATABASE__URL=' "$PROJECT_DIR/.env" | sed 's|.*://[^:]*:\([^@]*\)@.*|\1|')

if [ -z "$NEON_PASSWORD" ]; then
    echo "ERROR: Could not extract password from .env" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
FILENAME="couplefins-${TIMESTAMP}.sql.gz"
FILEPATH="$BACKUP_DIR/$FILENAME"

echo "Backing up Neon → $FILENAME"

docker exec -e PGPASSWORD="$NEON_PASSWORD" -e PGSSLMODE=require couplefins-postgres \
    pg_dump \
    --host="$NEON_HOST" \
    --username="$NEON_USER" \
    --dbname="$NEON_DB" \
    --no-owner \
    --no-privileges \
    --format=plain \
    --exclude-schema=neon_auth \
    | gzip > "$FILEPATH"

SIZE=$(du -h "$FILEPATH" | cut -f1)
echo "Done: $FILENAME ($SIZE)"

# Prune backups older than retention
PRUNED=$(find "$BACKUP_DIR" -name "couplefins-*.sql.gz" -mtime +"$RETENTION_DAYS" -print -delete | wc -l | tr -d ' ')
if [ "$PRUNED" -gt 0 ]; then
    echo "Pruned $PRUNED backup(s) older than ${RETENTION_DAYS} days"
fi
