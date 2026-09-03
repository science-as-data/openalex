# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A working repository of notes, examples, and tools for OpenAlex — a free, open
catalog of scholarly works. It is for the maintainer's and collaborators' own
use; it is **not** a published website. Everything is plain Markdown, Python,
Bash, and SQL — there is no build step, no test suite, and no linter config.

The repo mirrors the **two ways to access OpenAlex**, plus one cross-database
task:

- `api/` — the live REST API: quick reference, topic taxonomy notes, a worked
  example with committed CSVs, and the `get_subfields.py` CLI.
- `datadump/` — the bulk S3 snapshot: a complete pipeline that downloads the
  ~712 GB snapshot and loads it into a normalized PostgreSQL 18 schema on a
  dedicated SSD. This is the substantive engineering in the repo.
- `matching/` — crosswalk between OpenAlex journals and Scopus sources
  (Elsevier Serial Title API + the free Scopus Source List) so journals and
  their articles can be sampled by Scopus metadata (ASJC discipline). Design
  and calibration notes are in `matching/README.md`.

## Commands

```bash
# --- api/ ---
python api/get_subfields.py --list              # list the 26 fields
python api/get_subfields.py "Computer Science"  # subfields by name
python api/get_subfields.py 17                  # subfields by numeric ID

# --- datadump/scripts/  (all scripts cd to their own dir; run from anywhere) ---
./run_all.sh                       # full pipeline: prep -> download -> db -> load
./run_all.sh --from db --yes       # resume at a phase: prep | download | db | load
./run_all.sh --skip-download
./download.sh topics sources       # sync only selected entities (resumable)
./load.sh                          # schema -> every entity -> indexes -> VACUUM ANALYZE
./load.sh works authors            # partial reload (skips schema + indexes)
./load.sh --keep-csv --no-indexes
python flatten.py works --limit 100 --jobs 4    # JSONL -> CSV shards for one entity
python gen_sql.py schema  > sql/01_create_schema.sql    # regenerate after editing oa_schema.py
python gen_sql.py indexes > sql/02_create_indexes.sql
python gen_sql.py copy --csv DIR --entity works | psql   # what load.sh pipes per entity
sudo -u postgres ./smoke_test.sh   # the only test: one real S3 part-file per entity, throwaway DB
sudo ./restore_normal_config.sh    # post-load: drop bulk tuning, re-enable apt timers

# --- matching/  (needs the loaded DB; ELSEVIER_API_KEY in .env only for `fetch`) ---
python match.py schema             # create scopus/matching schemas, refresh candidate view
python match.py sourcelist         # load the public Scopus Source List xlsx (no key)
python match.py fetch --max-calls 15000   # Serial Title API, cached + quota-aware, resumable
python match.py resolve            # ISSN -> exact title -> fuzzy title cascade -> crosswalk
python match.py review / export / stats   # data/review_queue.csv, data/crosswalk.csv, stats_*.csv
python normalize.py --test; python linkage.py --test; python scopus_client.py --test
```

`smoke_test.sh` is the pipeline's test. **Run it after any change to
`oa_schema.py`** — it catches column/type mismatches before a multi-day real
load. `psql -U simone -h localhost -d openalex` connects to the loaded DB.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx pandas matplotlib requests python-dotenv tqdm   # api/
pip install --user awscli                                          # datadump/ (public bucket, no creds)
```

The CLI needs no API key. Refreshing the `exploring-subfields` data needs a
`.env` at the repo root with `OPENALEX_API_KEY` and optionally `OPENALEX_MAILTO`.
The datadump scripts need `~/.pgpass` (written by `set_password.sh`) for the
`simone` Postgres role; the password is never written to any committed file.

## Architecture: the datadump pipeline

### `oa_schema.py` is the single source of truth

`datadump/scripts/oa_schema.py` defines three things that must stay in lockstep,
and the rest of the pipeline is generated from it:

- `ENTITIES` — load order (lookups first, `works` last).
- `TABLES[entity][table]` — ordered `(column, sql_type)` lists. Each entity
  becomes a main table plus child tables for its nested arrays
  (`works_authorships`, `works_topics`, `authors_affiliations`, …).
- `EXTRACTORS[entity]` — a function turning one JSON record into
  `{table: [row_dict, ...]}`. **Row-dict keys must match `TABLES` column names**;
  `flatten.py` writes `row.get(col)` for each column, so a typo silently yields
  NULLs rather than an error.
- `POST_LOAD_INDEXES[entity][table]` — `("pk", cols)` / `("idx", cols)` specs
  applied only after the bulk load.

Consumers:

- `flatten.py` imports `EXTRACTORS` + `TABLES` and fans `part_*.gz` files across
  a process pool, writing headerless gzipped CSV shards to
  `<csv>/<entity>/<table>/<updated_date>_<part>.csv.gz`.
- `gen_sql.py` imports `TABLES` + `POST_LOAD_INDEXES` and emits `CREATE TABLE`,
  `\copy ... FROM PROGRAM 'gunzip -c ...'` (with explicit column lists), and
  index SQL. The `copy` output is piped straight into psql by `load.sh`.
- `sql/01_create_schema.sql` and `sql/02_create_indexes.sql` are **generated
  and committed** for review. After editing `oa_schema.py`, regenerate both
  (commands above) — `load.sh` and `smoke_test.sh` read the committed files,
  not `gen_sql.py` directly.
- `sql/03_add_foreign_keys.sql` is **hand-maintained**, not generated. When
  adding or dropping a table, edit its FK `ALTER`s by hand. All FKs are
  `NOT VALID` on purpose: snapshots contain orphan references, so a VALIDATE
  pass would fail on real data. They exist for introspection tools and the
  planner, not for enforcement.

Conventions baked into the schema: IDs are kept as full OpenAlex URLs
(`https://openalex.org/W…`) so every `*_id` column joins directly; genuinely
nested or variadic blobs (`abstract_inverted_index`, `apc_list`, `lineage`,
`issn`, …) are `jsonb` via the `j()` helper; `summary_stats` is unpacked by
`stats()`. `datadump/db_schema.svg` is a hand-drawn ERD of the loaded DB; update
it if tables change.

### Load orchestration

`run_all.sh` drives phases in order and is the only script that uses `sudo`
inline. It creates the ssd2 directories, runs `download.sh`, feeds the
`~/.pgpass` password into `00_setup_db.sql` as a psql variable (tablespace
`openalex_ts` + `openalex` DB + `simone` role), installs
`postgresql-bulkload.conf` as a conf.d drop-in, runs `load.sh` as the current
user, then removes the drop-in unless `KEEP_TUNING=1`.

`load.sh` per entity: flatten → `\copy` shards → delete shards, so only one
entity's transient CSVs exist at a time. Primary keys and indexes are built
once at the end. Passing entity names implies a partial reload and skips both
schema creation and indexing.

The bulk-tuning drop-in turns off `autovacuum` and `synchronous_commit` and is
unsafe to leave in place. `restore_normal_config.sh` removes it, refuses to run
while a VACUUM/INDEX/PK session is active, and re-enables the apt-daily timers
that are masked during long index builds so unattended-upgrades cannot restart
Postgres mid-build.

All paths default to `/media/simone/ssd2/openalex/{snapshot,csv,pgdata}` and
are overridable via `OPENALEX_ROOT`, `OPENALEX_SNAPSHOT`, `OPENALEX_CSV`,
`PGDATABASE`, `PSQL`, `JOBS`, `PG_CONFD`, `AWS`.

### Snapshot format facts that shape the code

- Target: OpenAlex **standard-format snapshot, RELEASE 2026-03-30** (walden
  format, 2025-11-12 onwards). The official 2022 gist scripts target the retired
  `venues`/`host_venue` model and silently drop most entities; this pipeline
  replaces them.
- Walden dropped `works.grants` (now the `awards` entity + `works_awards`) and
  zeroed `concepts.{ancestors,related_concepts,counts_by_year}`. Those four
  child tables were deliberately removed; do not re-add them. See the
  "Tables intentionally not modeled" section of `datadump/README.md`.
- `download.sh` syncs only `s3://openalex/data/` — the bucket also has a
  ~290 GB `legacy-data/` tree nothing here reads. Tiny lookup lists
  (`countries`, `languages`, `licenses`, …) are shipped but not loaded.
- `flatten.py` skips records with no `id`. Refreshes are full reloads;
  `merged_ids/` deletions are not applied automatically.

## Architecture: the api/ arm

`api/exploring-subfields.md` documents a two-phase flow: (1) fetch `/subfields`
and `/works` with `httpx.Client` (retry on 429) and write 15 CSVs to `api/data/`;
(2) read the combined CSVs back with pandas and chart with matplotlib. The CSVs
are committed — force-added past the `data/` pattern in `.gitignore` — so the
example reproduces without an API key. Use `git add -f` when updating them.

`api/get_subfields.py` is a standalone `requests` script with no dependency on
the rest of the repo.

## OpenAlex API Essentials

- **Base URL**: `https://api.openalex.org`
- **Auth**: free API key as `?api_key=YOUR_KEY`; `mailto` param for the polite pool
- **Rate limits**: 100,000 credits/day, max 100 req/s
- **Credit costs**: single entity = 0, list = 1, search = 10, semantic search = 1,000
- **Entities**: Works, Authors, Sources, Institutions, Topics, Publishers, Funders
  (the snapshot adds Awards, Keywords, Concepts, and the Domain/Field/Subfield hierarchy)
- **Topic hierarchy**: Domain (4) → Field (26) → Subfield (252) → Topic (~4,500)
- **Cursor paging** for >10K results: `?cursor=*`, follow `next_cursor`
- **Filter operators**: AND (comma), OR (pipe), NOT (`!`), inequality (`<`/`>`)
- List endpoints take `per-page` (hyphen) as a query param.
