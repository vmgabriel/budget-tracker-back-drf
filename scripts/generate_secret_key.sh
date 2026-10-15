#!/usr/bin/env bash
#
# Generate a Django secret key.
#
#   scripts/generate_secret_key.sh              # print the key
#   scripts/generate_secret_key.sh --env-file   # print "DJANGO_SECRET_KEY=<key>"
#
# The value is written to stdout only, so it can be piped straight into a
# secret manager or a .env file without leaking through a terminal scrollback
# command:
#
#   DJANGO_SECRET_KEY=$(scripts/generate_secret_key.sh)
#
# Django uses this one secret for several purposes: signing session cookies,
# CSRF tokens, password-reset tokens, and (through SimpleJWT's SIGNING_KEY) the
# access and refresh tokens themselves. Anyone holding it can mint a token for
# any user, which is why it must be unique per environment, at least 50
# characters, and kept in a secret manager rather than in source control.
#
# Rotating it invalidates every issued token and session. Rotate deliberately,
# not by accident: a rotation during a release logs every user out.

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage: generate_secret_key.sh [--env-file] [--help]

  --env-file   Prefix the output with "DJANGO_SECRET_KEY=" so it can be
               appended directly to a .env file.
  --help       Show this message.
EOF
}

EMIT_ENV_PREFIX=false

for argument in "$@"; do
    case "$argument" in
        --env-file)
            EMIT_ENV_PREFIX=true
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $argument" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# Prefer the project's own interpreter so the generated entropy and character
# set match what Django will accept; fall back to any available Python 3.
PYTHON_BIN=""
for candidate in "${PYTHON:-}" python3 python; do
    if [[ -n "$candidate" ]] && command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if [[ -z "$PYTHON_BIN" ]]; then
    echo "ERROR: no python3 interpreter found on PATH." >&2
    exit 1
fi

# 64 random bytes in URL-safe base64: 86 characters, ~512 bits of entropy.
# secrets.token_urlsafe draws from the operating system CSPRNG, not from a
# seeded generator, so two runs never produce the same key.
KEY="$("$PYTHON_BIN" - <<'PYTHON'
import secrets

print(secrets.token_urlsafe(64))
PYTHON
)"

if [[ ${#KEY} -lt 50 ]]; then
    echo "ERROR: generated key is too short; refusing to emit it." >&2
    exit 1
fi

if [[ "$EMIT_ENV_PREFIX" == true ]]; then
    printf 'DJANGO_SECRET_KEY=%s\n' "$KEY"
else
    printf '%s\n' "$KEY"
fi