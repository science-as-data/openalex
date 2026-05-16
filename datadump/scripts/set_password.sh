#!/usr/bin/env bash
# Prompt for the `simone` Postgres role password and store it in ~/.pgpass.
#
# The password is typed interactively (never echoed, never an argv, never
# committed). ~/.pgpass lets psql authenticate automatically afterwards, so you
# only ever type it here.  00_setup_db.sql / run_all.sh read it back from here.
#
#   ./set_password.sh
set -euo pipefail

PGPASS="$HOME/.pgpass"
LINE_HOST="localhost"
LINE_PORT="5432"
LINE_USER="simone"

read -rs -p "Password for Postgres role '$LINE_USER': " p1; echo
read -rs -p "Confirm: " p2; echo

[[ -n "$p1" ]]        || { echo "error: empty password" >&2; exit 1; }
[[ "$p1" == "$p2" ]]  || { echo "error: passwords don't match" >&2; exit 1; }
# ~/.pgpass uses ':' as a field separator and '\' as its escape char; psql
# \set would also choke on those. Keep the password free of both.
case "$p1" in
    *:*|*\\*) echo "error: password must not contain ':' or '\\'" >&2; exit 1 ;;
esac

umask 077
touch "$PGPASS"
chmod 600 "$PGPASS"

tmp="$(mktemp)"
# keep every line except a prior entry for this role, then append the new one
grep -v ":${LINE_USER}:" "$PGPASS" > "$tmp" 2>/dev/null || true
printf '%s:%s:*:%s:%s\n' "$LINE_HOST" "$LINE_PORT" "$LINE_USER" "$p1" >> "$tmp"
mv "$tmp" "$PGPASS"
chmod 600 "$PGPASS"

echo "stored password for role '$LINE_USER' in $PGPASS (chmod 600)."
echo "next:  ./run_all.sh   (or re-run 00_setup_db.sql to apply it to the role)"
