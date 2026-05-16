# OpenAlex Data Dump

Working with the full OpenAlex snapshot — fetching it and loading it into a
local PostgreSQL 18 database.

OpenAlex publishes a complete **bulk export** of its catalog — every work,
author, source, institution, topic, publisher, funder, and more — as compressed
JSON Lines files on Amazon S3. For analysis over hundreds of millions of
records, the data dump avoids API rate limits and credit costs entirely: you
download once, then query locally.

This directory holds the tooling to do that. It targets the **OpenAlex
standard-format snapshot, RELEASE 2026-03-30**, loaded into a normalized
relational schema on a dedicated SSD.

> **Note on the official scripts.** OpenAlex's docs link 2022-era gist scripts
> (`flatten-openalex-jsonl.py` etc.) that target the retired `venues` /
> `host_venue` data model. They silently drop most of a current snapshot
> (`sources`, `topics`, `keywords`, `awards`, `publishers`, `funders`,
> `locations`, …). The `scripts/` here are a rewrite against the current model.

## What the dump contains

Measured from the S3 `manifest` files (RELEASE 2026-03-30):

| Entity | Compressed | Records | Notes |
|---|--:|--:|---|
| works | 639 GB | 492.4 M | the bulk of everything |
| authors | 70 GB | 113.6 M | |
| awards | 3.0 GB | 12.2 M | grant/award records |
| sources | 347 MB | 280 K | journals, repositories, conferences |
| institutions | 177 MB | 121 K | |
| concepts | 6.8 MB | 65 K | deprecated, still shipped |
| funders | 9.4 MB | 32 K | |
| publishers | 1.8 MB | 11 K | |
| keywords | 2.1 MB | 65 K | |
| topics / subfields / fields / domains | ~5 MB | 4.5 K / 252 / 26 / 4 | the topic hierarchy |

**~712 GB compressed** total. Each entity is a directory of gzipped JSON Lines
files: `data/<entity>/updated_date=YYYY-MM-DD/part_NNN.gz`, one JSON object per
line. The snapshot also ships small flat lookup lists (`countries`,
`languages`, `licenses`, `sdgs`, `work-types`, …) which this tooling does not
load — they are tiny and rarely needed as tables.

## Target layout on disk

Everything lives on the dedicated SSD at `/media/simone/ssd2`:

```
/media/simone/ssd2/openalex/
  snapshot/   raw S3 sync (~712 GB, kept for re-loads & incremental updates)
  csv/        transient flattened CSV shards (one entity at a time, then deleted)
  pgdata/     the `openalex_ts` tablespace — all openalex.* tables & indexes
```

The existing PG18 cluster stays on the system disk; only the `openalex`
database is placed on ssd2 via a tablespace. Expect the loaded database
(tables + indexes) to land around **1.5–2 TB**.

## Loading procedure

All commands run from `datadump/scripts/`. Steps marked **(sudo)** need root.

### Phase 0 — disk prep & AWS CLI

```bash
# (sudo) create the ssd2 directories with the right ownership
# NB: run with bash -c, not sh -c — POSIX sh does not brace-expand {a,b,c}
sudo bash -c '
  root=/media/simone/ssd2/openalex
  mkdir -p "$root"/snapshot "$root"/csv "$root"/pgdata
  chown simone:simone "$root" "$root"/snapshot "$root"/csv
  chown postgres:postgres "$root"/pgdata
  chmod 700 "$root"/pgdata
'
# AWS CLI (no account needed — the bucket is public)
pip install --user awscli
```

### Phase 1 — download the snapshot

```bash
./download.sh                 # full ~712 GB sync; resumable, just re-run it
# or a subset while testing:  ./download.sh topics sources institutions
```

### Phase 2 — database, tablespace, load tuning

```bash
# pick a password for the `simone` Postgres role — stored only in ~/.pgpass
./set_password.sh

# (sudo) tablespace + `openalex` database, both rooted on ssd2
#   the password is fed to psql as a variable, never written into the SQL file
DBPASS=$(awk -F: '$4=="simone"{print $5}' ~/.pgpass)
printf '\set db_password %s\n' "$DBPASS" | cat - 00_setup_db.sql \
    | sudo -u postgres psql -v ON_ERROR_STOP=1

# (sudo) temporary bulk-load tuning — see the file's header for the revert steps
sudo cp postgresql-bulkload.conf /etc/postgresql/18/main/conf.d/
sudo systemctl reload postgresql
```

Or skip all of the above and just run `./run_all.sh`, which drives Phases 0–6
in order (it calls `set_password.sh`'s output for you).

### Phase 3–6 — flatten, COPY, index, analyze

```bash
./load.sh                     # schema -> every entity -> indexes -> VACUUM ANALYZE
```

`load.sh` walks the entities lookup-first, works-last. For each it runs
`flatten.py` (JSONL → gzipped CSV shards, parallel across all cores), `\copy`s
the shards in, then deletes them — so only one entity's transient CSVs exist at
a time. Indexes and primary keys are built once at the end, when it is far
cheaper than maintaining them during the load.

Then revert the tuning (per `postgresql-bulkload.conf`'s header) and re-enable
autovacuum.

### Verify it worked

`smoke_test.sh` runs the entire pipeline on one real part-file per entity into a
throwaway database — run it after any change to `oa_schema.py`:

```bash
sudo -u postgres ./smoke_test.sh
```

## The schema

A normalized relational schema in the `openalex` Postgres schema. Each entity
becomes a main table plus child tables for its nested arrays — e.g. `works`,
`works_authorships`, `works_authorship_institutions`, `works_locations`,
`works_topics`, `works_referenced_works`, `works_counts_by_year`, …; `authors`,
`authors_affiliations`, `authors_counts_by_year`; and so on. IDs are kept as
full OpenAlex URLs (`https://openalex.org/W…`) so every `*_id` column joins
directly. Genuinely nested/variadic blobs (`abstract_inverted_index`,
`apc_list`, `lineage`, `issn`, …) are stored as `jsonb`.

`scripts/oa_schema.py` is the **single source of truth**: it defines every
table's columns/types *and* the per-record extractor functions.
`scripts/gen_sql.py` generates the `CREATE TABLE`, `\copy`, and index SQL from
it, so the CSVs and the schema can never drift apart. The generated
`sql/01_create_schema.sql` and `sql/02_create_indexes.sql` are committed for
review; regenerate with `python gen_sql.py schema|indexes`.

## `scripts/` contents

| File | Purpose |
|---|---|
| `oa_schema.py` | tables, column types, and per-record extractors — the source of truth |
| `flatten.py` | `python flatten.py <entity>` — JSONL → gzipped CSV shards, parallel |
| `gen_sql.py` | generates schema / index / `\copy` SQL from `oa_schema.py` |
| `download.sh` | `aws s3 sync` the snapshot (full or selected entities) |
| `set_password.sh` | prompt for the `simone` role password, store it in `~/.pgpass` |
| `00_setup_db.sql` | tablespace + `openalex` database + login role |
| `run_all.sh` | one-shot driver for Phases 0–6 |
| `postgresql-bulkload.conf` | temporary load-tuning drop-in (revert after) |
| `load.sh` | orchestrator: schema → flatten+COPY per entity → indexes → analyze |
| `smoke_test.sh` | full pipeline on one part-file per entity, throwaway DB |
| `sql/01_create_schema.sql` | generated `CREATE TABLE`s |
| `sql/02_create_indexes.sql` | generated primary keys + indexes |

## Incremental updates

OpenAlex ships a new release roughly every few weeks. To refresh:

1. Re-run `./download.sh` — `aws s3 sync` pulls only new/changed `part_*.gz`
   files and new `updated_date=` partitions.
2. The snapshot also publishes `data/merged_ids/` (entities merged away since
   the last release) — deletions to apply by hand; the current tooling does a
   full reload rather than a diff/merge.

For now the simplest correct refresh is a full `./load.sh` against the
re-synced snapshot.

## Links

- [OpenAlex snapshot docs](https://docs.openalex.org/download-all-data/openalex-snapshot) — official guide
- [Snapshot data format](https://docs.openalex.org/download-all-data/snapshot-data-format)
- [API arm](../api/) — for lookups and small queries, use the REST API instead
