#!/usr/bin/env bash
#
# Timestamped PostgreSQL backup with automatic retention.
#
#   scripts/backup_db.sh                      # writes to ./backups
#   BACKUP_DIR=/srv/backups scripts/backup_db.sh
#
# Designed to be run either from the host (against a published PostgreSQL port)
# or from inside the Compose network:
#
#   docker compose exec db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump ...'
#
# The recommended host-cron invocation, which needs no published database port:
#
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#       exec -T db sh -lc 'cd / && /scripts/backup_db.sh'
#
# see the Deployment section of the README for the full cron entry.

set -Eeuo pipefail

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

# Destination directory. Default matches a bind/named mount so the host keeps
# the dumps even after the container is replaced.
BACKUP_DIR="${BACKUP_DIR:-/backups}"

# Database connection. Inside the db container POSTGRES_* are already set, so
# the defaults work there; on the host, export DATABASE_URL or the parts.
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-budget_tracker}}"
PGUSER="${PGUSER:-${POSTGRES_USER:-budget_tracker}}"

# Password: taken from the environment (PGPASSWORD or POSTGRES_PASSWORD) and
# never from an argument, because arguments are visible in the process list.
: "${PGPASSWORD:=${POSTGRES_PASSWORD:-}}"

# libpq reads PG* from the environment of the pg_dump process, not from this
# shell's locals. Without an explicit export, PGHOST, PGUSER, and PGPASSWORD set
# above stay in this shell and pg_dump falls back to a local socket with no
# password, which is the classic "no password supplied" failure.
export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD

# How many days of backups to keep. Old dumps are deleted after the new one is
# written, so a failed run never removes the only good copy.
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Where the run journal goes. Cron mails nothing and a container's own logs are
# rotated away, so a run that failed silently would leave no trace at all: this
# file is the record an operator checks to answer "did the backup run, and did
# it verify?".
BACKUP_LOG="${BACKUP_LOG:-${BACKUP_DIR}/backup.log}"

# Compression level for the custom format (0-9). 6 is pg_dump's default.
COMPRESSION_LEVEL="${COMPRESSION_LEVEL:-6}"

# Set to 1 to skip retention pruning (useful for a first dry run).
SKIP_PRUNE="${SKIP_PRUNE:-0}"

SCRIPT_NAME="$(basename "$0")"

log() { printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
fail() {
    log "ERROR: $*" >&2
    exit 1
}

# Append a line to the run journal. Written after BACKUP_DIR is validated, so a
# misconfigured directory fails loudly instead of silently logging nowhere.
journal() {
    printf '%s %s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" "$2" \
        >>"${BACKUP_LOG}" 2>/dev/null || true
}

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

command -v pg_dump >/dev/null 2>&1 || fail \
    "pg_dump is not installed. Use the postgres:16-alpine image or install postgresql-client."

[[ -n "${PGDATABASE}" ]] || fail "PGDATABASE is empty; set it or POSTGRES_DB."
[[ -n "${PGUSER}" ]] || fail "PGUSER is empty; set it or POSTGRES_USER."

if [[ -z "${PGPASSWORD}" ]]; then
    # Trust/peer auth is a legitimate setup, so this is a warning, not a stop.
    log "WARNING: no password supplied; relying on .pgpass, PGPASSWORD, or trust auth."
fi

mkdir -p "${BACKUP_DIR}" || fail "Cannot create backup directory: ${BACKUP_DIR}"
[[ -w "${BACKUP_DIR}" ]] || fail "Backup directory is not writable: ${BACKUP_DIR}"

# The journal lives next to the dumps. Created up front and marked started, so
# a run that dies hard (a killed container, a full disk) still leaves evidence
# that it began.
touch "${BACKUP_LOG}" || fail "Cannot write the run journal: ${BACKUP_LOG}"
journal "START" "database=${PGDATABASE} retention_days=${RETENTION_DAYS}"

# Enough free space for one more dump; a full disk mid-run leaves a truncated
# file that looks like a valid backup.
AVAILABLE_MB="$(df -Pm "${BACKUP_DIR}" | awk 'NR==2 {print $4}')"
if [[ "${AVAILABLE_MB}" =~ ^[0-9]+$ ]] && [[ "${AVAILABLE_MB}" -lt 100 ]]; then
    fail "Less than 100 MB free in ${BACKUP_DIR} (${AVAILABLE_MB} MB available)."
fi

# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------

TIMESTAMP="$(date -u '+%Y%m%d_%H%M%S')"
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.dump"

log "Dumping database '${PGDATABASE}' (${PGUSER}@${PGHOST}:${PGPORT})."

# -Fc  custom format: compressed, and restorable with pg_restore (selective,
#                     parallel). Plain SQL would need pg_dump/psql instead.
# -f -   stream to stdout so nothing partial is left behind under the final
#         name if pg_dump dies mid-stream.
# Written to a temporary file first and moved into place only on success, so a
# crash never leaves a truncated dump that a restore would happily attempt.
TEMP_FILE="${BACKUP_FILE}.partial"

pg_dump \
    --format=custom \
    --compress="${COMPRESSION_LEVEL}" \
    --no-owner \
    --no-privileges \
    --file="${TEMP_FILE}"

[[ -s "${TEMP_FILE}" ]] || fail "pg_dump produced an empty file."

mv "${TEMP_FILE}" "${BACKUP_FILE}"

BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
log "Wrote ${BACKUP_FILE} (${BACKUP_SIZE})."
journal "DUMPED" "file=${BACKUP_FILE} size=${BACKUP_SIZE}"

# A dump that cannot be listed is not a backup. Verify the archive catalog
# before declaring success.
if command -v pg_restore >/dev/null 2>&1; then
    if CATALOG="$(pg_restore --list "${BACKUP_FILE}" 2>&1)"; then
        OBJECT_COUNT="$(printf '%s\n' "${CATALOG}" | grep -c '^[0-9]' || true)"
        log "Verified the archive catalog with pg_restore --list (${OBJECT_COUNT} entries)."
        journal "VERIFIED" "file=${BACKUP_FILE} entries=${OBJECT_COUNT}"
    else
        # Kept out of the journal's happy path on purpose: an unverified dump is
        # worse than no dump, because the next run's retention may prune the
        # last good copy while this one looks like a file on disk.
        journal "VERIFY_FAILED" "file=${BACKUP_FILE}"
        printf '%s\n' "${CATALOG}" >&2
        fail "Archive verification failed for ${BACKUP_FILE}; treat it as unusable."
    fi
else
    log "WARNING: pg_restore is unavailable, so the archive was not verified."
    journal "UNVERIFIED" "file=${BACKUP_FILE} reason=pg_restore-missing"
fi

# A backup nobody has restored is a hope, not a plan. The timestamped name
# makes the restore target unambiguous.
cat <<EOF

Restore with:
  scripts/restore_db.sh ${BACKUP_FILE}          # --dry-run first; it lists the archive
  pg_restore --clean --if-exists --no-owner --dbname <target-database> ${BACKUP_FILE}

EOF

# --------------------------------------------------------------------------
# Retention
# --------------------------------------------------------------------------

if [[ "${SKIP_PRUNE}" == "1" ]]; then
    log "Retention skipped (SKIP_PRUNE=1)."
    journal "DONE" "file=${BACKUP_FILE} pruned=0 (SKIP_PRUNE=1)"
    exit 0
fi

if [[ ! "${RETENTION_DAYS}" =~ ^[0-9]+$ ]]; then
    journal "FAILED" "reason=invalid RETENTION_DAYS=${RETENTION_DAYS}"
    fail "RETENTION_DAYS must be a non-negative integer, got '${RETENTION_DAYS}'."
fi

log "Deleting backups older than ${RETENTION_DAYS} day(s) in ${BACKUP_DIR}."
DELETED="$(find "${BACKUP_DIR}" -maxdepth 1 -type f \
    -name 'backup_*.dump' \
    -mtime "+${RETENTION_DAYS}" \
    -print -delete | wc -l | tr -d ' ')"

log "Retention complete: ${DELETED} file(s) removed."
journal "DONE" "file=${BACKUP_FILE} pruned=${DELETED}"

exit 0