#!/usr/bin/env bash
# Post-load cleanup: restore normal PostgreSQL config + re-enable apt-daily timers.
#
# Run this AFTER 02_create_indexes.sql, 03_add_foreign_keys.sql, and the
# follow-up VACUUM ANALYZE have all finished. It:
#   1. Removes the bulk-load conf drop-in (which disables autovacuum and sets
#      synchronous_commit=off — unsafe for normal operation).
#   2. Reloads postgres so the defaults take effect.
#   3. Unmasks and restarts apt-daily timers (masked during the build to
#      prevent unattended-upgrades from restarting postgres mid-index).
#
# Requires sudo. Idempotent — safe to re-run.

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "This script needs root. Re-run with: sudo $0" >&2
  exit 1
fi

CONF=/etc/postgresql/18/main/conf.d/postgresql-bulkload.conf

# --- safety check: refuse to run while a vacuum/index is still active --------
ACTIVE=$(sudo -u postgres psql -d openalex -tAc "
  SELECT count(*) FROM pg_stat_activity
  WHERE state='active'
    AND (query ILIKE '%VACUUM%' OR query ILIKE '%CREATE INDEX%' OR query ILIKE '%ADD PRIMARY KEY%')
    AND pid != pg_backend_pid();
" 2>/dev/null || echo 0)

if [[ "$ACTIVE" -gt 0 ]]; then
  echo "Refusing to run: $ACTIVE active VACUUM/INDEX/PK session(s) still in flight." >&2
  echo "Wait for them to finish, then re-run." >&2
  exit 2
fi

# --- 1. drop the bulk-load conf ----------------------------------------------
if [[ -f "$CONF" ]]; then
  echo "Removing $CONF"
  rm -f "$CONF"
  echo "Reloading postgres..."
  systemctl reload postgresql
else
  echo "$CONF already absent — skipping conf removal."
fi

# --- 2. re-enable apt-daily timers -------------------------------------------
for unit in apt-daily.timer apt-daily-upgrade.timer; do
  if systemctl is-enabled --quiet "$unit" 2>/dev/null; then
    echo "$unit already enabled — skipping."
  else
    echo "Unmasking + starting $unit"
    systemctl unmask "$unit" 2>/dev/null || true
    systemctl enable --now "$unit"
  fi
done

# --- 3. verify ----------------------------------------------------------------
echo
echo "=== verification ==="
echo "-- bulk-load conf present? (should be 'absent') --"
[[ -f "$CONF" ]] && echo "STILL PRESENT: $CONF" || echo "absent"
echo
echo "-- postgres effective settings --"
sudo -u postgres psql -d openalex -c "
  SELECT name, setting, source
  FROM pg_settings
  WHERE name IN ('autovacuum','synchronous_commit','maintenance_work_mem','max_wal_size')
  ORDER BY name;
"
echo "-- apt-daily timer state --"
systemctl is-enabled apt-daily.timer apt-daily-upgrade.timer
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer --no-pager | head -5

echo
echo "Done."
