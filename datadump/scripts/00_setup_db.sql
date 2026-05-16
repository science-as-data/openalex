-- Phase 2a - tablespace, database, and role for the OpenAlex load.
--
-- Run as the postgres superuser. The `simone` role password is supplied as a
-- psql variable `db_password` so it never lives in this committed file:
--
--   ./set_password.sh                      # stores the password in ~/.pgpass
--   DBPASS=$(awk -F: '$4=="simone"{print $5}' ~/.pgpass)
--   printf '\set db_password %s\n' "$DBPASS" | cat - 00_setup_db.sql \
--       | sudo -u postgres psql -v ON_ERROR_STOP=1
--
-- (run_all.sh does exactly this for you.)
--
-- Safe to re-run: the tablespace / role / database are each created only if
-- missing. The tablespace directory must already exist and be owned by postgres:
--   sudo install -d -o postgres -g postgres -m 700 /media/simone/ssd2/openalex/pgdata

\if :{?db_password}
\else
  \echo 'ERROR: psql variable db_password is not set - run ./set_password.sh first'
  -- raise a real error so callers (ON_ERROR_STOP) see a non-zero exit...
  DO $$ BEGIN RAISE EXCEPTION 'db_password not set'; END $$;
  -- ...and stop here even when ON_ERROR_STOP is off, before anything is created.
  \quit
\endif

-- tablespace (created only if missing)
SELECT format('CREATE TABLESPACE openalex_ts LOCATION %L',
              '/media/simone/ssd2/openalex/pgdata')
WHERE NOT EXISTS (SELECT 1 FROM pg_tablespace WHERE spcname = 'openalex_ts')
\gexec

-- login role for day-to-day querying: created if missing, password (re)set
-- either way from the db_password variable.
SELECT format('CREATE ROLE simone LOGIN CREATEDB PASSWORD %L', :'db_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'simone')
\gexec
ALTER ROLE simone LOGIN CREATEDB PASSWORD :'db_password';

-- database, rooted on the ssd2 tablespace (created only if missing)
SELECT 'CREATE DATABASE openalex '
       'TABLESPACE openalex_ts OWNER simone ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'openalex')
\gexec

\connect openalex
GRANT ALL ON SCHEMA public TO simone;
ALTER DATABASE openalex SET search_path = openalex, public;
