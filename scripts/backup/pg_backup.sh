#!/usr/bin/env bash
# Automated Postgres backup for Nowing (self-managed VPS / Dokploy container).
# - pg_dump custom format (-Fc), timestamped, integrity-checked, rotated.
# - Optional off-site upload via rclone.
# - Read-only w.r.t. the database. Safe to run daily via cron/systemd.
#
# Config via env (or edit defaults). Secrets (PGPASSWORD) via env or ~/.pgpass — never hardcode.
set -Eeuo pipefail

: "${PGHOST:=127.0.0.1}"
: "${PGPORT:=5432}"
: "${PGUSER:=postgres}"
: "${PGDATABASE:=nowing}"
# For Dokploy where DB has no host-exposed port, set DOCKER_CONTAINER=<pg container name>
# and the script will pg_dump via `docker exec` instead of TCP.
: "${DOCKER_CONTAINER:=}"

BACKUP_DIR="${BACKUP_DIR:-/opt/nowing-remediation-backups}"
KEEP_DAILY="${KEEP_DAILY:-14}"       # keep last N daily dumps
KEEP_WEEKLY="${KEEP_WEEKLY:-8}"      # keep last N Sunday dumps
RCLONE_REMOTE="${RCLONE_REMOTE:-}"   # e.g. "b2:nowing-backups" (empty = skip off-site)
LOG="${LOG:-$BACKUP_DIR/backup.log}"

ts="$(date -u +%Y%m%dT%H%M%SZ)"
dow="$(date -u +%u)"                 # 7 = Sunday
mkdir -p "$BACKUP_DIR"
log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG" >&2; }
out="$BACKUP_DIR/nowing-${ts}.dump"

log "START backup -> $out (db=$PGDATABASE ${DOCKER_CONTAINER:+container=$DOCKER_CONTAINER}${DOCKER_CONTAINER:-host=$PGHOST:$PGPORT})"

# 1) Dump (custom format, compressed)
if [ -n "$DOCKER_CONTAINER" ]; then
  docker exec -e PGPASSWORD="${PGPASSWORD:-}" "$DOCKER_CONTAINER" \
    pg_dump -U "$PGUSER" -Fc -Z6 "$PGDATABASE" > "$out"
else
  pg_dump -Fc -Z6 -f "$out"   # uses PGHOST/PGPORT/PGUSER/PGDATABASE/PGPASSWORD env
fi

# 2) Integrity check (verify TOC is readable & non-trivial)
entries="$(pg_restore --list "$out" | grep -cv '^;' || true)"
if [ "${entries:-0}" -lt 10 ]; then
  log "ERROR: dump TOC has only ${entries:-0} entries — likely corrupt/empty. Aborting."
  exit 1
fi
log "OK verified: $entries TOC entries, size $(du -h "$out" | cut -f1)"

# 3) Weekly retained copy (Sunday)
if [ "$dow" = "7" ]; then cp "$out" "$BACKUP_DIR/weekly-nowing-${ts}.dump"; log "weekly copy created"; fi

# 4) Off-site (optional)
if [ -n "$RCLONE_REMOTE" ]; then
  rclone copy "$out" "$RCLONE_REMOTE/" && log "off-site uploaded -> $RCLONE_REMOTE" || log "WARN off-site upload failed"
fi

# 5) Rotation (prune old dailies/weeklies beyond retention)
ls -1t "$BACKUP_DIR"/nowing-*.dump 2>/dev/null | tail -n +"$((KEEP_DAILY+1))" | xargs -r rm -f
ls -1t "$BACKUP_DIR"/weekly-nowing-*.dump 2>/dev/null | tail -n +"$((KEEP_WEEKLY+1))" | xargs -r rm -f

log "DONE (retention: ${KEEP_DAILY} daily / ${KEEP_WEEKLY} weekly)"
