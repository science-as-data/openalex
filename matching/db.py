"""PostgreSQL access for the matching tool (psycopg 3).

Connection: ``OPENALEX_DSN`` if set, else ``dbname=openalex user=simone
host=localhost`` with the password from ~/.pgpass (written by
datadump/scripts/set_password.sh).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

DEFAULT_DSN = "dbname=openalex user=simone host=localhost"


def connect(dsn: str | None = None) -> psycopg.Connection:
    return psycopg.connect(dsn or os.environ.get("OPENALEX_DSN", DEFAULT_DSN))


def upsert_source(cur: psycopg.Cursor, rec: dict, origin: str) -> bool:
    """Insert/refresh one Scopus source and its child rows.

    API rows win: a 'sourcelist' record never overwrites an 'api' record.
    Returns True when the row was written (and children replaced).
    """
    cur.execute(
        """
        INSERT INTO scopus.sources (scopus_source_id, title, publisher, source_type,
            coverage_start, coverage_end, coverage_text, is_active, oa_status,
            origin, raw, fetched_at)
        VALUES (%(scopus_source_id)s, %(title)s, %(publisher)s, %(source_type)s,
            %(coverage_start)s, %(coverage_end)s, %(coverage_text)s, %(is_active)s,
            %(oa_status)s, %(origin)s, %(raw)s, %(fetched_at)s)
        ON CONFLICT (scopus_source_id) DO UPDATE SET
            title = EXCLUDED.title, publisher = EXCLUDED.publisher,
            source_type = EXCLUDED.source_type,
            coverage_start = EXCLUDED.coverage_start, coverage_end = EXCLUDED.coverage_end,
            coverage_text = coalesce(EXCLUDED.coverage_text, scopus.sources.coverage_text),
            is_active = EXCLUDED.is_active, oa_status = EXCLUDED.oa_status,
            origin = EXCLUDED.origin, raw = EXCLUDED.raw, fetched_at = EXCLUDED.fetched_at
        WHERE scopus.sources.origin <> 'api' OR EXCLUDED.origin = 'api'
        RETURNING scopus_source_id
        """,
        {**{k: rec.get(k) for k in ("scopus_source_id", "title", "publisher", "source_type",
                                    "coverage_start", "coverage_end", "coverage_text",
                                    "is_active", "oa_status")},
         "origin": origin,
         "raw": Jsonb(rec.get("raw")) if rec.get("raw") is not None else None,
         "fetched_at": datetime.now(timezone.utc)})
    if cur.fetchone() is None:
        return False
    sid = rec["scopus_source_id"]
    cur.execute("DELETE FROM scopus.source_issns WHERE scopus_source_id = %s", (sid,))
    cur.execute("DELETE FROM scopus.source_asjc WHERE scopus_source_id = %s", (sid,))
    if rec.get("issns"):
        cur.executemany(
            "INSERT INTO scopus.source_issns VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            [(sid, i, k) for i, k in rec["issns"]])
    if rec.get("asjc"):
        cur.executemany(
            "INSERT INTO scopus.source_asjc VALUES (%s, %s) ON CONFLICT DO NOTHING",
            [(sid, a[0]) for a in rec["asjc"]])
        cur.executemany(
            "INSERT INTO scopus.asjc (code, abbrev, name) VALUES (%s, %s, %s) "
            "ON CONFLICT (code) DO UPDATE SET abbrev = coalesce(EXCLUDED.abbrev, scopus.asjc.abbrev), "
            "name = coalesce(EXCLUDED.name, scopus.asjc.name)",
            [(a[0], a[1], a[2]) for a in rec["asjc"] if len(a) == 3])
    if rec.get("metrics"):
        cur.execute("DELETE FROM scopus.source_metrics WHERE scopus_source_id = %s", (sid,))
        cur.executemany(
            "INSERT INTO scopus.source_metrics VALUES (%s, %s, %s, %s, %s)",
            [(sid, y, m.get("citescore"), m.get("snip"), m.get("sjr"))
             for y, m in sorted(rec["metrics"].items())])
    return True


def load_scopus_sources(cur: psycopg.Cursor) -> list[dict]:
    """Every Scopus source with its ISSNs, for the resolver."""
    cur.execute(
        """
        SELECT s.scopus_source_id, s.title, s.publisher, s.source_type,
               s.coverage_start, s.coverage_end, s.origin,
               coalesce(array_agg(i.issn) FILTER (WHERE i.issn IS NOT NULL), '{}') AS issns
        FROM scopus.sources s
        LEFT JOIN scopus.source_issns i USING (scopus_source_id)
        GROUP BY s.scopus_source_id
        """)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load_oa_candidates(cur: psycopg.Cursor, min_works: int = 0,
                       active_since: int | None = None, limit: int | None = None,
                       require_issn: bool = False) -> list[dict]:
    where = ["works_count >= %(min_works)s"]
    if active_since:
        where.append("coalesce(last_publication_year, 0) >= %(active_since)s")
    if require_issn:
        where.append("cardinality(issns_n) > 0")
    cur.execute(
        f"""
        SELECT oa_source_id, display_name, alternate_titles, publisher, country_code,
               works_count, first_publication_year, last_publication_year,
               issn_l_n, issns_n
        FROM matching.oa_journal_candidates
        WHERE {' AND '.join(where)}
        ORDER BY works_count DESC, oa_source_id
        {'LIMIT %(limit)s' if limit else ''}
        """,
        {"min_works": min_works, "active_since": active_since, "limit": limit})
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def write_map(cur: psycopg.Cursor, rows: list[dict], run_id: str) -> None:
    """Replace the automatic crosswalk rows with this run's result."""
    cur.execute("DELETE FROM matching.oa_scopus_source_map")
    cur.executemany(
        """
        INSERT INTO matching.oa_scopus_source_map
            (oa_source_id, scopus_source_id, match_method, tier, score,
             is_best_for_oa, is_best_for_scopus, evidence, decided_by, run_id)
        VALUES (%(oa_source_id)s, %(scopus_source_id)s, %(match_method)s, %(tier)s,
                %(score)s, %(is_best_for_oa)s, %(is_best_for_scopus)s, %(evidence)s,
                %(decided_by)s, %(run_id)s)
        ON CONFLICT (oa_source_id, scopus_source_id) DO UPDATE SET
            match_method = EXCLUDED.match_method, tier = EXCLUDED.tier,
            score = EXCLUDED.score, is_best_for_oa = EXCLUDED.is_best_for_oa,
            is_best_for_scopus = EXCLUDED.is_best_for_scopus,
            evidence = EXCLUDED.evidence, decided_by = EXCLUDED.decided_by,
            decided_at = now(), run_id = EXCLUDED.run_id
        """,
        [{**r, "evidence": Jsonb(r.get("evidence") or {}), "run_id": run_id} for r in rows])
