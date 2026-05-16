#!/usr/bin/env bash
# One-shot driver for the whole OpenAlex -> PostgreSQL load (Phases 0-6).
#
# Runs every step from the README in order. The sudo-requiring steps are called
# with `sudo` inline, so you'll be prompted for your password once near the
# start (the timestamp cache covers the rest).
#
#   ./run_all.sh                 # full run: prep -> download -> db -> load
#   ./run_all.sh --skip-download # snapshot already synced
#   ./run_all.sh --from db       # start at a phase: prep | download | db | load
#   ./run_all.sh --yes           # don't pause for the pre-download confirmation
#
# Env (all have sane defaults):
#   OPENALEX_ROOT   base dir on the SSD   (default /media/simone/ssd2/openalex)
#   PG_CONFD        cluster conf.d dir    (default /etc/postgresql/18/main/conf.d)
#   KEEP_TUNING     1 = leave bulk-load tuning in place after the load (default 0)
set -euo pipefail
cd "$(dirname "$0")"
SCRIPTS="$PWD"

OPENALEX_ROOT="${OPENALEX_ROOT:-/media/simone/ssd2/openalex}"
PG_CONFD="${PG_CONFD:-/etc/postgresql/18/main/conf.d}"
KEEP_TUNING="${KEEP_TUNING:-0}"
export OPENALEX_SNAPSHOT="$OPENALEX_ROOT/snapshot"
export OPENALEX_CSV="$OPENALEX_ROOT/csv"
AWS="${AWS:-$(command -v aws || echo "$HOME/.local/bin/aws")}"

START_PHASE="prep"
SKIP_DOWNLOAD=0
ASSUME_YES=0
for arg in "$@"; do
    case "$arg" in
        --skip-download) SKIP_DOWNLOAD=1 ;;
        --from)          ;;                      # value consumed below
        prep|download|db|load) START_PHASE="$arg" ;;
        --yes|-y)        ASSUME_YES=1 ;;
        *) echo "unknown arg: $arg" >&2; exit 2 ;;
    esac
done

# phase ordering helper: should we run phase $1 given START_PHASE?
order() { case "$1" in prep) echo 0;; download) echo 1;; db) echo 2;; load) echo 3;; esac; }
run_phase() { [[ $(order "$1") -ge $(order "$START_PHASE") ]]; }

ts()   { date '+%F %T'; }
step() { echo; echo "=========  [$(ts)]  $*  ========="; }

# password for the `simone` role, read back from ~/.pgpass (set by ./set_password.sh)
pgpass_password() { awk -F: '$4=="simone"{print $5; exit}' "$HOME/.pgpass" 2>/dev/null; }

# ---------------------------------------------------------------------------
step "preflight"
# ---------------------------------------------------------------------------
if [[ ! -x "$AWS" ]] && ! command -v "$AWS" >/dev/null 2>&1; then
    echo "aws CLI not found. Install it first:  pip install --user awscli" >&2
    exit 1
fi
echo "aws CLI:        $AWS"
echo "snapshot dir:   $OPENALEX_SNAPSHOT"
echo "csv scratch:    $OPENALEX_CSV"
echo "tablespace dir: $OPENALEX_ROOT/pgdata"
echo "pg conf.d:      $PG_CONFD"
echo "starting at phase: $START_PHASE"
sudo -v   # prompt for the password now, once

# fail fast: the db phase needs a ~/.pgpass password unless the db already exists
if run_phase db && ! sudo -u postgres psql -tAc \
        "SELECT 1 FROM pg_database WHERE datname='openalex'" 2>/dev/null | grep -q 1; then
    if [[ -z "$(pgpass_password)" ]]; then
        echo "ERROR: role 'simone' has no password in ~/.pgpass." >&2
        echo "       run ./set_password.sh first." >&2
        exit 1
    fi
    echo "simone password:  found in ~/.pgpass"
fi

# ---------------------------------------------------------------------------
if run_phase prep; then
step "Phase 0 - create ssd2 directories (sudo)"
sudo sh -c "
    mkdir -p '$OPENALEX_ROOT'/snapshot '$OPENALEX_ROOT'/csv '$OPENALEX_ROOT'/pgdata
    chown $(id -un):$(id -gn) '$OPENALEX_ROOT' '$OPENALEX_ROOT'/snapshot '$OPENALEX_ROOT'/csv
    chown postgres:postgres '$OPENALEX_ROOT'/pgdata
    chmod 700 '$OPENALEX_ROOT'/pgdata
"
echo "directories ready:"
ls -ld "$OPENALEX_ROOT"/snapshot "$OPENALEX_ROOT"/csv "$OPENALEX_ROOT"/pgdata
fi

# ---------------------------------------------------------------------------
if run_phase download && [[ $SKIP_DOWNLOAD -eq 0 ]]; then
step "Phase 1 - download the snapshot (~712 GB compressed)"
if [[ $ASSUME_YES -eq 0 ]]; then
    read -r -p "This downloads ~712 GB to $OPENALEX_SNAPSHOT. Continue? [y/N] " ans
    [[ "$ans" == [yY]* ]] || { echo "aborted."; exit 1; }
fi
"$SCRIPTS/download.sh"
elif run_phase download; then
step "Phase 1 - download SKIPPED (--skip-download)"
fi

# ---------------------------------------------------------------------------
if run_phase db; then
step "Phase 2 - tablespace, database, bulk-load tuning (sudo)"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='openalex'" \
        | grep -q 1; then
    echo "database 'openalex' already exists - skipping 00_setup_db.sql"
else
    DBPASS="$(pgpass_password)"
    if [[ -z "$DBPASS" ]]; then
        echo "no password for role 'simone' in ~/.pgpass." >&2
        echo "run ./set_password.sh first, then re-run with --from db." >&2
        exit 1
    fi
    # feed the password as a psql variable via stdin so it never hits argv
    { printf '\\set db_password %s\n' "$DBPASS"; cat "$SCRIPTS/00_setup_db.sql"; } \
        | sudo -u postgres psql -v ON_ERROR_STOP=1
fi
sudo install -d "$PG_CONFD"
sudo cp "$SCRIPTS/postgresql-bulkload.conf" "$PG_CONFD/"
sudo systemctl reload postgresql
echo "bulk-load tuning installed and cluster reloaded."
fi

# ---------------------------------------------------------------------------
if run_phase load; then
step "Phases 3-6 - flatten, COPY, index, analyze"
# Runs as the current user (not postgres): psql \copy ... FROM PROGRAM is
# client-side, needs no superuser, and the snapshot/CSV dirs are simone-owned.
# psql connects to the openalex DB as role `simone` (peer auth over the socket,
# or ~/.pgpass over TCP).
OPENALEX_SNAPSHOT="$OPENALEX_SNAPSHOT" \
OPENALEX_CSV="$OPENALEX_CSV" \
PGDATABASE="openalex" \
    bash "$SCRIPTS/load.sh"

step "Phase 6 - revert bulk-load tuning"
if [[ "$KEEP_TUNING" == "1" ]]; then
    echo "KEEP_TUNING=1 - leaving $PG_CONFD/postgresql-bulkload.conf in place."
else
    sudo rm -f "$PG_CONFD/postgresql-bulkload.conf"
    sudo systemctl reload postgresql
    echo "tuning drop-in removed, cluster reloaded (autovacuum back on)."
fi
fi

step "all done"
echo "Connect with:  psql -U simone -h localhost -d openalex"
