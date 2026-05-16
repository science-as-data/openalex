#!/usr/bin/env python3
"""Flatten one OpenAlex entity's gzipped JSON Lines into gzipped CSV shards.

    python flatten.py <entity> [--snapshot DIR] [--csv DIR] [--jobs N] [--limit N]

For entity ``works`` this fans every ``part_*.gz`` file out across a process
pool; each worker writes one CSV shard per relational table into
``<csv>/<entity>/<table>/<shard>.csv.gz``.  Shards carry **no header row** --
``copy.sql`` lists the columns explicitly and globs the shard directory.

Reads the table layout and per-record extractors from ``oa_schema.py`` so the
CSV columns can never drift from the SQL schema.
"""

import argparse
import csv
import glob
import gzip
import json
import os
import sys
from multiprocessing import Pool

import oa_schema

DEFAULT_SNAPSHOT = os.environ.get("OPENALEX_SNAPSHOT",
                                  "/media/simone/ssd2/openalex/snapshot")
DEFAULT_CSV = os.environ.get("OPENALEX_CSV", "/media/simone/ssd2/openalex/csv")


def shard_name(jsonl_path):
    """Stable, collision-free shard id from a .../updated_date=DATE/part_NNN.gz path."""
    parts = jsonl_path.split(os.sep)
    date = next((p.split("=", 1)[1] for p in parts if p.startswith("updated_date=")),
                "nodate")
    base = os.path.basename(jsonl_path).replace(".gz", "")
    return f"{date}_{base}"


def process_file(args):
    entity, jsonl_path, csv_dir, limit = args
    tables = oa_schema.TABLES[entity]
    extract = oa_schema.EXTRACTORS[entity]
    shard = shard_name(jsonl_path)

    writers, handles = {}, {}
    for table, cols in tables.items():
        out_path = os.path.join(csv_dir, entity, table, shard + ".csv.gz")
        fh = gzip.open(out_path, "wt", newline="", encoding="utf-8")
        handles[table] = fh
        writers[table] = (csv.writer(fh), [c for c, _ in cols])

    n = 0
    try:
        with gzip.open(jsonl_path, "rt", encoding="utf-8") as src:
            for line in src:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if not rec.get("id"):
                    continue
                for table, rows in extract(rec).items():
                    writer, colnames = writers[table]
                    for row in rows:
                        writer.writerow([row.get(c) for c in colnames])
                n += 1
                if limit and n >= limit:
                    break
    finally:
        for fh in handles.values():
            fh.close()
    return jsonl_path, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entity", choices=oa_schema.ENTITIES)
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--limit", type=int, default=0,
                    help="max records per input file (smoke testing)")
    args = ap.parse_args()

    entity = args.entity
    in_glob = os.path.join(args.snapshot, "data", entity, "*", "*.gz")
    files = sorted(glob.glob(in_glob))
    if not files:
        sys.exit(f"no input files matched {in_glob}")

    for table in oa_schema.TABLES[entity]:
        os.makedirs(os.path.join(args.csv, entity, table), exist_ok=True)

    print(f"[{entity}] {len(files)} files -> {args.jobs} workers", flush=True)
    tasks = [(entity, f, args.csv, args.limit) for f in files]
    total = 0
    with Pool(args.jobs) as pool:
        for i, (path, n) in enumerate(pool.imap_unordered(process_file, tasks), 1):
            total += n
            if i % 50 == 0 or i == len(files):
                print(f"[{entity}] {i}/{len(files)} files, {total:,} records",
                      flush=True)
    print(f"[{entity}] done: {total:,} records", flush=True)


if __name__ == "__main__":
    main()
