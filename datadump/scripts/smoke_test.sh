#!/usr/bin/env bash
# End-to-end smoke test - no full download, no tablespace needed.
#
# Pulls one real part file per entity straight from S3 over HTTPS, runs the
# whole flatten -> schema -> COPY -> index pipeline into a throwaway database,
# prints row counts, and drops it. Run this after editing oa_schema.py to catch
# column / type mismatches before committing to the ~712 GB real load.
#
#   ./smoke_test.sh            # uses `psql` (peer auth: run as the postgres user)
#   PSQL='psql -U simone -h localhost' ./smoke_test.sh
set -euo pipefail
cd "$(dirname "$0")"

PSQL="${PSQL:-psql} -v ON_ERROR_STOP=1 --quiet"
SMOKE_DB="${SMOKE_DB:-openalex_smoke}"
TMP="$(mktemp -d)"
SNAP="$TMP/snapshot" CSV="$TMP/csv"
trap 'rm -rf "$TMP"; ${PSQL% *} -c "DROP DATABASE IF EXISTS $SMOKE_DB;" >/dev/null 2>&1 || true' EXIT

ENTITIES=$(python3 -c 'import oa_schema; print(*oa_schema.ENTITIES)')
BASE="https://openalex.s3.amazonaws.com"

echo ">>> fetching one part file per entity from S3"
for e in $ENTITIES; do
    url=$(curl -s "$BASE/data/$e/manifest" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['entries'][0]['url'].replace('s3://openalex/','$BASE/'))")
    d="$SNAP/data/$e/updated_date=smoke"
    mkdir -p "$d"
    curl -s "$url" -o "$d/part_000.gz"
    printf '  %-14s %s\n' "$e" "$(du -h "$d/part_000.gz" | cut -f1)"
done

echo ">>> flattening"
for e in $ENTITIES; do
    python3 flatten.py "$e" --snapshot "$SNAP" --csv "$CSV" --jobs 4 >/dev/null
done

echo ">>> creating throwaway database $SMOKE_DB"
${PSQL% *} -c "DROP DATABASE IF EXISTS $SMOKE_DB;"
${PSQL% *} -c "CREATE DATABASE $SMOKE_DB;"

echo ">>> schema + COPY + indexes"
PGDATABASE="$SMOKE_DB" $PSQL -f sql/01_create_schema.sql
PGDATABASE="$SMOKE_DB" python3 gen_sql.py copy --csv "$CSV" | PGDATABASE="$SMOKE_DB" $PSQL
PGDATABASE="$SMOKE_DB" $PSQL -f sql/02_create_indexes.sql

echo ">>> row counts:"
PGDATABASE="$SMOKE_DB" ${PSQL% *} -At -c "
SELECT relname, n_live_tup
FROM pg_stat_user_tables WHERE schemaname='openalex'
ORDER BY relname;" | sed 's/^/  /'

echo ">>> SMOKE TEST PASSED"
