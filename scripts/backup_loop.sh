#!/usr/bin/env bash
#
# Periodic database backup sidecar.
#
# Runs scripts/backup_db.sh once immediately and then every
# BACKUP_INTERVAL_SECONDS (default 86400 = daily) until the container is
# stopped. It is the command of the Compose `backup` service, where a sleep loop
# is used instead of cron because the postgres image ships no cron daemon and
# adding one would mean a second image to keep patched.
#
#   /scripts/backup_loop.sh                       # daily, writing to /backups
#   BACKUP_INTERVAL_SECONDS=3600 /scripts/backup_loop.sh
#
# The first run is immediate on purpose: a stack that starts at 09:00 must not
# wait until 09:00 the next day for its first backup.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# The dump command itself. Overridable so the loop can drive a wrapper (for
# example one that ships the dump off-host) without editing this file.
BACKUP_SCRIPT="${BACKUP_SCRIPT:-${SCRIPT_DIR}/backup_db.sh}"

# Seconds between runs. BACKUP_INTERVAL_SECONDS is the name the Compose service
# sets; RETENTION_DAYS is handled by backup_db.sh, not here.
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

# Set to 1 while a shutdown signal has been received, so the loop can finish the
# current run and exit before starting another.
stopping=0

log() { printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }
fail() {
    log "ERROR: $*" >&2
    exit 1
}

# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

[[ -x "${BACKUP_SCRIPT}" ]] || fail "Backup script is missing or not executable: ${BACKUP_SCRIPT}"

if ! [[ "${INTERVAL}" =~ ^[0-9]+$ ]] || [[ "${INTERVAL}" -lt 1 ]]; then
    fail "BACKUP_INTERVAL_SECONDS must be a positive integer, got '${INTERVAL}'."
fi

# --------------------------------------------------------------------------
# Shutdown handling
# --------------------------------------------------------------------------

# A SIGTERM must not kill pg_dump mid-stream. The signal only raises a flag; the
# loop checks it between runs, so an in-flight dump always finishes and is
# verified. backup_db.sh already writes to a .partial file and renames it on
# success, so even a hard kill leaves no file that looks like a whole backup.
on_stop() {
    if [[ "${stopping}" == "0" ]]; then
        log "Shutdown requested; will stop after the current run."
        stopping=1
    fi
}
trap on_stop TERM INT

sleep_between_runs() {
    # Sleep in one-second slices so a SIGTERM is honoured within a second
    # instead of after a full 24-hour interval.
    local remaining="${INTERVAL}"
    while [[ "${remaining}" -gt 0 && "${stopping}" == "0" ]]; do
        sleep 1
        remaining=$((remaining - 1))
    done
}

# --------------------------------------------------------------------------
# Loop
# --------------------------------------------------------------------------

log "Backup loop started: interval=${INTERVAL}s script=${BACKUP_SCRIPT}."

while [[ "${stopping}" == "0" ]]; do
    log "Starting scheduled backup."
    if "${BACKUP_SCRIPT}"; then
        log "Scheduled backup finished."
    else
        status=$?
        # A failed run must not stop the loop: the next interval is the retry,
        # and backup_db.sh has already journalled the reason. Surfacing the exit
        # code keeps the failure visible in the container's log stream.
        log "Scheduled backup failed (exit ${status}); will retry next interval."
    fi

    [[ "${stopping}" == "1" ]] && break

    sleep_between_runs
done

log "Backup loop stopped."
exit 0
