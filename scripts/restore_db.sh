#!/usr/bin/env bash
#
# Restore a custom-format PostgreSQL backup written by scripts/backup_db.sh.
#
#   scripts/restore_db.sh --dry-run backups/backup_20240101_030000.dump
#   scripts/restore_db.sh --yes      backups/backup_20240101_030000.dump
#   PGDATABASE=budget_tracker_scratch scripts/restore_db.sh --yes backup_*.dump
#
# Safety model, because a restore is the one operation that can destroy the
# data it is meant to protect:
#
#   * The target is never guessed: it comes from --database, PGDATABASE, or
#     POSTGRES_DB, and a real restore is refused until the operator confirms the
#     database name (or passes --yes). A dry run touches no database at all.
#   * --dry-run validates the archive and prints exactly what a real run would
#     do, without opening a connection. Run it first, always.
#   * A real restore refuses to proceed without --yes. When no terminal is
#     attached and --yes is absent, it fails instead of hanging on a prompt.
#   * pg_restore runs with --clean --if-exists, which drops and recreates every
#     object in the target. Restore into a scratch database first, verify the
#     row counts, and only then decide to touch the live one.
#
# Connection: standard libpq variables (PGHOST, PGPORT, PGUSER, PGPASSWORD) or
# a .pgpass file. Inside the Compose network the defaults already point at db.

set -Eeuo pipefail

SCRIPT_NAME="$(basename "$0")"

# --------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------

DRY_RUN=0
ASSUME_YES=0
CLEAN=1
BACKUP_FILE_ARG=""

# How many TOC entries --list must report for the archive to count as non-empty.
MIN_ARCHIVE_ENTRIES=1

usage() {
    cat <<EOF
Usage: ${SCRIPT_NAME} [options] <backup-file>

Restore a custom-format pg_dump archive into an explicitly named database.

Options:
  -n, --dry-run        Validate the archive and print the plan; touch no
                       database. Recommended before every real restore.
  -y, --yes            Skip the interactive confirmation. Required when no
                       terminal is attached.
      --no-clean       Do not pass --clean --if-exists. Use only when the
                       target database is empty; otherwise the restore will
                       collide with existing objects.
      --database=NAME  Restore target. Overrides PGDATABASE.
  -h, --help           Show this message.

Environment:
  PGDATABASE / POSTGRES_DB   Restore target (one of them is required).
  PGHOST / PGPORT / PGUSER / PGPASSWORD   Connection (libpq defaults apply).

Examples:
  ${SCRIPT_NAME} --dry-run backups/backup_20240101_030000.dump
  PGDATABASE=scratch ${SCRIPT_NAME} --yes backups/backup_20240101_030000.dump
EOF
}

while [[ $# -gt 0 ]]; do
    argument="$1"
    case "${argument}" in
        -n | --dry-run) DRY_RUN=1 ;;
        -y | --yes) ASSUME_YES=1 ;;
        --no-clean) CLEAN=0 ;;
        --database=*) PGDATABASE="${argument#--database=}" ;;
        -h | --help)
            usage
            exit 0
            ;;
        --)
            # Everything after -- is positional (the file).
            shift
            break
            ;;
        -*)
            printf 'Unknown option: %s\n\n' "${argument}" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [[ -n "${BACKUP_FILE_ARG}" ]]; then
                printf 'Only one backup file may be given.\n' >&2
                exit 2
            fi
            BACKUP_FILE_ARG="${argument}"
            ;;
    esac
    shift
done

# Anything left after a -- separator is the file argument.
if [[ $# -gt 0 ]]; then
    [[ -z "${BACKUP_FILE_ARG}" ]] || {
        printf 'Only one backup file may be given.\n' >&2
        exit 2
    }
    BACKUP_FILE_ARG="$1"
fi

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

log() { printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
fail() {
    log "ERROR: $*" >&2
    exit 1
}

# --------------------------------------------------------------------------
# Resolve the archive
# --------------------------------------------------------------------------

BACKUP_FILE="${BACKUP_FILE_ARG:-${BACKUP_FILE:-}}"
[[ -n "${BACKUP_FILE}" ]] || fail "No backup file given. See '${SCRIPT_NAME} --help'."

[[ -e "${BACKUP_FILE}" ]] || fail "Backup file does not exist: ${BACKUP_FILE}"
[[ -f "${BACKUP_FILE}" ]] || fail "Backup path is not a regular file: ${BACKUP_FILE}"
[[ -r "${BACKUP_FILE}" ]] || fail "Backup file is not readable: ${BACKUP_FILE}"
[[ -s "${BACKUP_FILE}" ]] || fail "Backup file is empty: ${BACKUP_FILE}"

# --------------------------------------------------------------------------
# Validation: the archive must be a readable custom/zlib/tar dump
# --------------------------------------------------------------------------

command -v pg_restore >/dev/null 2>&1 || fail \
    "pg_restore is not installed. Use the postgres:16-alpine image or install postgresql-client."

# The catalog listing is the validation: a file that pg_restore cannot list is
# either truncated, a plain-SQL dump, or a different format, and every one of
# those would fail part-way through a real restore.
if ! ARCHIVE_LIST="$(pg_restore --list "${BACKUP_FILE}" 2>&1)"; then
    printf '%s\n' "${ARCHIVE_LIST}" >&2
    fail "Not a usable pg_restore archive: ${BACKUP_FILE}. Refusing to continue."
fi

ENTRY_COUNT="$(printf '%s\n' "${ARCHIVE_LIST}" | grep -c '^[0-9]' || true)"
if [[ "${ENTRY_COUNT}" -lt "${MIN_ARCHIVE_ENTRIES}" ]]; then
    fail "Archive lists no objects (${ENTRY_COUNT}); it is empty or damaged."
fi

FILE_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
log "Archive OK: ${BACKUP_FILE} (${FILE_SIZE}, ${ENTRY_COUNT} catalog entries)."

# --------------------------------------------------------------------------
# Resolve the target
# --------------------------------------------------------------------------

PGDATABASE="${PGDATABASE:-${POSTGRES_DB:-}}"
PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-${POSTGRES_USER:-}}"

# --------------------------------------------------------------------------
# Dry run: print the plan and stop before touching any database
# --------------------------------------------------------------------------

if [[ "${DRY_RUN}" == "1" ]]; then
    printf '\n'
    log "DRY RUN: no database connection will be made and nothing will change."
    printf '\n%s\n\n' "--- Archive catalog (pg_restore --list) ---"
    printf '%s\n' "${ARCHIVE_LIST}"
    printf '\n%s\n\n' "--- Command a real run would execute ---"
    if [[ "${CLEAN}" == "1" ]]; then
        printf 'pg_restore --clean --if-exists --no-owner --no-privileges \\\n'
    else
        printf 'pg_restore --no-owner --no-privileges \\\n'
    fi
    printf '  --exit-on-error --single-transaction \\\n'
    printf '  --dbname="%s" "%s"\n\n' "${PGDATABASE:-<unset>}" "${BACKUP_FILE}"
    log "DRY RUN complete: re-run without --dry-run to apply."
    exit 0
fi

# --------------------------------------------------------------------------
# Validate the target (a real restore only)
# --------------------------------------------------------------------------

[[ -n "${PGDATABASE}" ]] || fail \
    "No restore target. Set PGDATABASE (or POSTGRES_DB), or pass --database=NAME."
[[ -n "${PGUSER}" ]] || fail "No restore user. Set PGUSER (or POSTGRES_USER)."

# Export so pg_restore and psql — separate processes — see the connection
# settings. Without the export, libpq silently falls back to a local socket and
# no password, which is how a restore ends up attempted against the wrong
# server.
export PGHOST PGPORT PGDATABASE PGUSER
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"

# Reachability first: a restore that fails after dropping objects because the
# server was never there is the worst outcome. pg_isready is a cheap check.
if command -v pg_isready >/dev/null 2>&1; then
    pg_isready --host="${PGHOST}" --port="${PGPORT}" --username="${PGUSER}" \
        --dbname="${PGDATABASE}" >/dev/null 2>&1 \
        || fail "Cannot reach database '${PGDATABASE}' at ${PGHOST}:${PGPORT} as ${PGUSER}."
fi

log "Restoring ${BACKUP_FILE} into '${PGDATABASE}' at ${PGHOST}:${PGPORT} as ${PGUSER}."

# --------------------------------------------------------------------------
# Confirmation
# --------------------------------------------------------------------------

if [[ "${CLEAN}" == "1" ]]; then
    log "WARNING: --clean --if-exists will DROP and recreate every object in '${PGDATABASE}'."
else
    log "WARNING: objects will be created into '${PGDATABASE}' without dropping existing ones."
fi

if [[ "${ASSUME_YES}" != "1" ]]; then
    if [[ ! -t 0 ]]; then
        fail "Refusing to restore without confirmation and no terminal is attached. Re-run with --yes."
    fi
    printf 'Type the target database name (%s) to confirm: ' "${PGDATABASE}" >&2
    read -r REPLY
    if [[ "${REPLY}" != "${PGDATABASE}" ]]; then
        fail "Confirmation did not match '${PGDATABASE}'; aborting without changes."
    fi
fi

# --------------------------------------------------------------------------
# Restore
# --------------------------------------------------------------------------

RESTORE_OPTIONS=(--no-owner --no-privileges --exit-on-error --single-transaction)
if [[ "${CLEAN}" == "1" ]]; then
    RESTORE_OPTIONS=(--clean --if-exists "${RESTORE_OPTIONS[@]}")
fi

# --single-transaction makes the whole restore atomic: a failure at any point
# rolls back, so the database is never left half-restored. It is incompatible
# with --jobs, which is why no parallelism is requested here.
if pg_restore \
    "${RESTORE_OPTIONS[@]}" \
    --dbname="${PGDATABASE}" \
    "${BACKUP_FILE}"; then
    log "Restore finished."
else
    fail "pg_restore failed; the transaction was rolled back, so '${PGDATABASE}' is unchanged."
fi

# --------------------------------------------------------------------------
# Post-restore sanity check
# --------------------------------------------------------------------------

if command -v psql >/dev/null 2>&1; then
    TABLE_COUNT="$(psql \
        --tuples-only --no-align \
        --command="SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" \
        2>/dev/null || printf '?')"
    log "Public schema now holds ${TABLE_COUNT} table(s). Verify the row counts before trusting it."
else
    log "psql is unavailable; verify the restored data with your own checklist."
fi

log "Done. Confirm the application is reading the expected data before removing any other copy."
exit 0
