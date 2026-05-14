# OpenAlex Data Dump

Working with the full OpenAlex snapshot.

OpenAlex publishes a complete **bulk export** of its catalog — every work,
author, source, institution, topic, publisher, and funder — as compressed
JSON Lines files on Amazon S3. For analysis over millions of records, the
data dump avoids API rate limits and credit costs entirely: you download
once, then query locally.

> **Work in progress.** The sections below are an outline to be filled in.

## What the dump contains

_TODO_ — the entity types exported, the JSON Lines format, file sizes, and
how the snapshot relates to the API's data model.

## Downloading the snapshot

The dump lives in a public, requester-pays-free S3 bucket. A full sync:

```bash
aws s3 sync "s3://openalex" "openalex-snapshot" --no-sign-request
```

_TODO_ — disk space requirements, syncing a single entity type, and using the
`manifest` files for incremental updates.

## On-disk layout

_TODO_ — the `data/<entity>/updated_date=.../` partition structure, the
`merged_ids` deletion files, and how snapshots are versioned by date.

## Loading and querying locally

_TODO_ — reading the gzipped JSONL with pandas / DuckDB / Spark, flattening
nested fields, and example queries.

## Links

- [OpenAlex snapshot docs](https://docs.openalex.org/download-all-data/openalex-snapshot) — official guide
- [API arm](../api/) — for lookups and small queries, use the REST API instead
