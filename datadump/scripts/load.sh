#!/usr/bin/env bash
# Phases 3-6 - flatten the snapshot, COPY it into Postgres, index, analyze.
#
#   ./load.sh                       # full load: schema -> all entities -> indexes
#   ./load.sh works authors         # only these entities (schema/index steps skipped)
#   ./load.sh --keep-csv            # don't delete CSV shards after each COPY
#   ./load.sh --skip-schema         # tables already exist, just (re)load data
#   ./load.sh --no-indexes          # stop before building indexes
#
# Per entity the flow is: flatten JSONL -> CSV shards, \copy shards into the
# table, then drop the shards before moving on -- so the transient CSVs for
# only one entity exist at a time, capping extra disk use.
#
# Env:
#   OPENALEX_SNAPSHOT  snapshot dir   (default /media/simone/ssd2/openalex/snapshot)
#   OPENALEX_CSV       CSV scratch dir(default /media/simone/ssd2/openalex/csv)
#   PGDATABASE         target db      (default openalex)
#   PSQL               psql command   (default: psql)
#   JOBS               flatten workers(default: nproc)
set -euo pipefail
cd "$(dirname "$0")"

SNAPSHOT="${OPENALEX_SNAPSHOT:-/media/simone/ssd2/openalex/snapshot}"
CSV="${OPENALEX_CSV:-/media/simone/ssd2/openalex/csv}"
export PGDATABASE="${PGDATABASE:-openalex}"
PSQL="${PSQL:-psql} -v ON_ERROR_STOP=1 --quiet"
JOBS="${JOBS:-$(nproc)}"

ALL_ENTITIES=$(python3 -c 'import oa_schema; print(*oa_schema.ENTITIES)')
KEEP_CSV=0 SKIP_SCHEMA=0 DO_INDEXES=1
ENTITIES=()
for arg in "$@"; do
    case "$arg" in
        --keep-csv)     KEEP_CSV=1 ;;
        --skip-schema)  SKIP_SCHEMA=1 ;;
        --no-indexes)   DO_INDEXES=0 ;;
        --*)            echo "unknown flag: $arg" >&2; exit 2 ;;
        *)              ENTITIES+=("$arg") ;;
    esac
done
# selecting specific entities implies a partial reload: skip schema + indexes
if [[ ${#ENTITIES[@]} -gt 0 ]]; then
    SKIP_SCHEMA=1; DO_INDEXES=0
else
    read -ra ENTITIES <<< "$ALL_ENTITIES"
fi

ts() { date '+%F %T'; }

if [[ $SKIP_SCHEMA -eq 0 ]]; then
    echo "[$(ts)] creating schema (drops + recreates openalex.* tables)"
    $PSQL -f sql/01_create_schema.sql
fi

for entity in "${ENTITIES[@]}"; do
    echo "[$(ts)] === $entity: flatten ==="
    python3 flatten.py "$entity" --snapshot "$SNAPSHOT" --csv "$CSV" --jobs "$JOBS"

    echo "[$(ts)] === $entity: COPY into Postgres ==="
    python3 gen_sql.py copy --csv "$CSV" --entity "$entity" | $PSQL

    if [[ $KEEP_CSV -eq 0 ]]; then
        echo "[$(ts)] === $entity: removing CSV shards ==="
        rm -rf "${CSV:?}/$entity"
    fi
done

if [[ $DO_INDEXES -eq 1 ]]; then
    echo "[$(ts)] building primary keys + indexes (this is the long tail)"
    $PSQL -f sql/02_create_indexes.sql
    echo "[$(ts)] VACUUM ANALYZE"
    $PSQL -c 'VACUUM ANALYZE;'
fi

echo "[$(ts)] load complete."
echo "Reminder: remove postgresql-bulkload.conf, re-enable autovacuum, reload."
