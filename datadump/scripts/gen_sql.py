#!/usr/bin/env python3
"""Generate the load SQL from oa_schema.py so it can never drift from the CSVs.

    python gen_sql.py schema                       # CREATE SCHEMA + CREATE TABLE
    python gen_sql.py indexes                      # ALTER TABLE ... PK + CREATE INDEX
    python gen_sql.py copy --csv DIR [--entity X]   # \\copy commands

`make_sql.sh` writes the first two to sql/ for review; `load.sh` pipes the
`copy` output straight into psql per entity.
"""

import argparse
import sys

import oa_schema

SCHEMA = "openalex"


def emit_schema():
    print(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA};\n")
    for entity in oa_schema.ENTITIES:
        for table, cols in oa_schema.TABLES[entity].items():
            print(f"DROP TABLE IF EXISTS {SCHEMA}.{table} CASCADE;")
            print(f"CREATE TABLE {SCHEMA}.{table} (")
            body = ",\n".join(f"    {c} {t}" for c, t in cols)
            print(body)
            print(");\n")


def emit_indexes():
    for entity in oa_schema.ENTITIES:
        for table, specs in oa_schema.POST_LOAD_INDEXES.get(entity, {}).items():
            for kind, cols in specs:
                collist = ", ".join(cols)
                if kind == "pk":
                    print(f"ALTER TABLE {SCHEMA}.{table} "
                          f"ADD PRIMARY KEY ({collist});")
                else:
                    name = f"{table}_{'_'.join(cols)}_idx"
                    print(f"CREATE INDEX IF NOT EXISTS {name} "
                          f"ON {SCHEMA}.{table} ({collist});")
        print()


def emit_copy(csv_dir, entities):
    for entity in entities:
        print(f"\\echo loading {entity}")
        for table, cols in oa_schema.TABLES[entity].items():
            collist = ", ".join(c for c, _ in cols)
            src = f"{csv_dir}/{entity}/{table}/*.csv.gz"
            print(
                f"\\copy {SCHEMA}.{table} ({collist}) "
                f"FROM PROGRAM 'gunzip -c {src}' WITH (FORMAT csv, NULL '')"
            )
        print()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("schema")
    sub.add_parser("indexes")
    cp = sub.add_parser("copy")
    cp.add_argument("--csv", required=True)
    cp.add_argument("--entity", choices=oa_schema.ENTITIES)
    args = ap.parse_args()

    if args.cmd == "schema":
        emit_schema()
    elif args.cmd == "indexes":
        emit_indexes()
    elif args.cmd == "copy":
        entities = [args.entity] if args.entity else oa_schema.ENTITIES
        emit_copy(args.csv.rstrip("/"), entities)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
