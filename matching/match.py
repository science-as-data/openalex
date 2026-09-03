#!/usr/bin/env python3
"""Match OpenAlex journals to Scopus sources and store the crosswalk.

Subcommands, in the order a full run uses them:

  schema       create the scopus/matching schemas and refresh the candidate view
  sourcelist   load the free Scopus Source List xlsx (ISSNs, ASJC, coverage)
  fetch        query the Serial Title API for journals not yet known (quota-aware)
  resolve      run the ISSN -> exact title -> fuzzy title cascade, write crosswalk
  review       export tier-2 pairs to data/review_queue.csv for a human
  export       write the accepted crosswalk to data/crosswalk.csv
  stats        coverage statistics (works in Scopus-indexed journals by year/area)
  eval-sample  draw a stratified sample for manual coding (fixed seed)
  eval-score   precision per tier from the coded sample

Secrets: ELSEVIER_API_KEY (+ optional ELSEVIER_INSTTOKEN) in the repo-root
.env. Database: OPENALEX_DSN or ~/.pgpass for `dbname=openalex user=simone`.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(HERE.parent / ".env")

import db  # noqa: E402
import linkage  # noqa: E402
from normalize import (fuzzy_forms, is_generic, norm_issn, publisher_key,  # noqa: E402
                       search_string, title_keys)

DATA = HERE / "data"
CACHE = HERE / "cache"
SQL = HERE / "sql" / "01_scopus_schema.sql"
OVERRIDES = HERE / "overrides.csv"


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def run_id() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, cwd=HERE).stdout.strip()
    except OSError:
        sha = "nogit"
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + (sha or "nogit")


# ============================================================== schema =======

def cmd_schema(args):
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute(SQL.read_text())
        if not args.no_refresh:
            log("refreshing matching.oa_journal_candidates ...")
            cur.execute("REFRESH MATERIALIZED VIEW matching.oa_journal_candidates")
            cur.execute("ANALYZE matching.oa_journal_candidates")
            cur.execute("SELECT count(*), count(*) FILTER (WHERE cardinality(issns_n) > 0) "
                        "FROM matching.oa_journal_candidates")
            n, n_issn = cur.fetchone()
            log(f"candidates: {n} journals, {n_issn} with a valid-looking ISSN")
        conn.commit()
    log("schema ok")


# ========================================================== sourcelist =======

_TYPE_MAP = {"journal": "journal", "trade journal": "tradejournal",
             "book series": "bookseries", "conference proceedings": "conferenceproceeding"}


def _col(df, *prefixes):
    for c in df.columns:
        lc = str(c).strip().lower()
        if any(lc.startswith(p) for p in prefixes):
            return c
    return None


def _coverage(text):
    """'2019-2024; 2016-2017' -> (2016, 2024); open-ended end -> None."""
    if not text or str(text).strip().lower() in ("nan", ""):
        return None, None, None
    starts, ends, open_end = [], [], False
    for seg in re.split(r"[;,]", str(text)):
        m = re.findall(r"\d{4}", seg)
        if not m:
            continue
        starts.append(int(m[0]))
        if len(m) >= 2:
            ends.append(int(m[-1]))
        elif re.search(r"(?i)present|ongoing|current|-\s*$", seg):
            open_end = True
        else:
            ends.append(int(m[0]))
    if not starts:
        return None, None, str(text)
    return min(starts), (None if open_end or not ends else max(ends)), str(text)


def download_sourcelist(dest_dir: Path) -> Path:
    import httpx
    page = "https://www.elsevier.com/products/scopus/content"
    log(f"looking for the Source List link on {page}")
    html = httpx.get(page, follow_redirects=True, timeout=60,
                     headers={"User-Agent": "Mozilla/5.0 openalex-matching"}).text
    m = re.search(r"(?:https?:)?//[^\s\"'\\]+ext_list[^\s\"'\\]*\.xlsx", html)
    if not m:
        raise SystemExit("could not find an ext_list*.xlsx link; download it manually "
                         "from that page and pass --file")
    url = m.group(0)
    if url.startswith("//"):
        url = "https:" + url
    dest = dest_dir / url.rsplit("/", 1)[-1]
    if dest.exists():
        log(f"already downloaded: {dest}")
        return dest
    log(f"downloading {url}")
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest


def cmd_sourcelist(args):
    import pandas as pd
    path = Path(args.file) if args.file else download_sourcelist(CACHE)
    xl = pd.ExcelFile(path)
    main = next((s for s in xl.sheet_names if s.lower().startswith("scopus sources")), xl.sheet_names[0])
    log(f"reading sheet {main!r} from {path.name}")
    df = xl.parse(main, dtype=str)
    c_id, c_title = _col(df, "sourcerecord id"), _col(df, "source title")
    c_issn, c_eissn = _col(df, "issn"), _col(df, "eissn")
    c_active, c_cov = _col(df, "active or inactive"), _col(df, "coverage")
    c_type, c_pub = _col(df, "source type"), _col(df, "publisher")
    c_asjc, c_oa = _col(df, "all science journal classification"), _col(df, "open access status")
    missing = [n for n, c in (("Sourcerecord ID", c_id), ("Source Title", c_title),
                              ("ISSN", c_issn), ("ASJC", c_asjc)) if c is None]
    if missing:
        raise SystemExit(f"unexpected Source List layout, missing columns: {missing}; "
                         f"have {list(df.columns)[:30]}")

    asjc_rows = []
    asjc_sheet = next((s for s in xl.sheet_names if "asjc" in s.lower()), None)
    if asjc_sheet:
        a = xl.parse(asjc_sheet, dtype=str, header=None)
        for _, row in a.iterrows():
            vals = [str(v).strip() for v in row.tolist() if str(v).strip() not in ("nan", "")]
            code = next((v for v in vals if re.fullmatch(r"\d{4}", v)), None)
            if code:
                desc = next((v for v in vals if v != code and not re.fullmatch(r"\d+", v)), None)
                asjc_rows.append((int(code), desc))

    n_ok = n_skip = 0
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        if asjc_rows:
            cur.executemany("INSERT INTO scopus.asjc (code, name) VALUES (%s, %s) "
                            "ON CONFLICT (code) DO UPDATE SET name = coalesce(scopus.asjc.name, EXCLUDED.name)",
                            asjc_rows)
            log(f"asjc lookup: {len(asjc_rows)} codes")
        for i, row in enumerate(df.itertuples(index=False, name=None), 1):
            r = dict(zip(df.columns, row))
            g = lambda c: (None if c is None else (None if str(r.get(c, "")).strip().lower() in ("nan", "") else str(r[c]).strip()))
            sid, title = g(c_id), g(c_title)
            if not sid or not title:
                n_skip += 1
                continue
            issns = []
            v = norm_issn(g(c_issn))
            if v:
                issns.append((v, "print"))
            v = norm_issn(g(c_eissn))
            if v and (v, "print") not in issns:
                issns.append((v, "electronic"))
            start, end, cov_text = _coverage(g(c_cov))
            active = (g(c_active) or "").lower().startswith("active") if c_active else None
            if active and end is not None and end >= datetime.now().year - 1:
                end = None            # still covered
            asjc = [(int(x), None, None) for x in re.findall(r"\d{4}", g(c_asjc) or "")]
            rec = {
                "scopus_source_id": sid.split(".")[0], "title": title, "publisher": g(c_pub),
                "source_type": _TYPE_MAP.get((g(c_type) or "").lower(), (g(c_type) or "").lower() or None),
                "coverage_start": start, "coverage_end": end, "coverage_text": cov_text,
                "is_active": active, "oa_status": g(c_oa),
                "issns": issns, "asjc": asjc, "metrics": {}, "raw": None,
            }
            n_ok += db.upsert_source(cur, rec, "sourcelist")
            if i % 5000 == 0:
                conn.commit()
                log(f"  {i} rows ...")
        conn.commit()
    log(f"sourcelist: {n_ok} sources written, {n_skip} rows skipped")


# =============================================================== fetch =======

def cmd_fetch(args):
    from scopus_client import BudgetExhausted, Cache, QuotaExceeded, ScopusClient
    client = ScopusClient(cache=Cache(CACHE / "scopus_api.sqlite"), reserve=args.reserve,
                          max_calls=args.max_calls, view=args.view, dry_run=args.dry_run)
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        oa = db.load_oa_candidates(cur, args.min_works, args.active_since, args.limit,
                                   require_issn=(args.mode == "issn"))
        cur.execute("SELECT issn FROM scopus.source_issns i JOIN scopus.sources s USING (scopus_source_id)"
                    + ("" if args.skip_known_any else " WHERE s.origin = 'api'"))
        known = {r[0] for r in cur.fetchall()}
        done = set() if args.refetch else client.cache.looked_up()
        log(f"{len(oa)} candidates; {len(known)} ISSNs already known; {len(done)} journals already looked up")

        n_found = n_miss = n_skipped = 0
        try:
            for k, o in enumerate(oa, 1):
                oid = o["oa_source_id"]
                issns = [x for x in [o["issn_l_n"]] + list(o["issns_n"] or []) if x]
                issns = [x for i, x in enumerate(issns) if x not in issns[:i]]
                if oid in done or (known and set(issns) & known):
                    n_skipped += 1
                    continue
                found = False
                if args.mode in ("issn", "both"):
                    for issn in issns[:2]:
                        r = client.issn_lookup(issn)
                        if not args.dry_run:
                            client.cache.record_lookup(oid, r.request_key)
                        if r.entries:
                            found = True
                            break
                if not found and args.mode in ("title", "both"):
                    queries = []
                    q1 = search_string(o["display_name"])
                    if q1 and not is_generic(o["display_name"]):
                        queries.append(q1)
                    alts = sorted((o["alternate_titles"] or []), key=len, reverse=True)
                    for alt in alts:
                        q2 = search_string(alt)
                        if q2 and not is_generic(alt) and (not q1 or
                                len(set(q2.lower().split()) ^ set(q1.lower().split())) > 3):
                            queries.append(q2)
                            break
                    for q in queries[:2]:
                        r = client.title_search(q, count=args.count)
                        if not args.dry_run:
                            client.cache.record_lookup(oid, r.request_key)
                        if r.entries:
                            found = True
                            break
                if found and not args.dry_run:
                    from scopus_client import parse_entry
                    for e in r.entries:
                        rec = parse_entry(e)
                        if rec:
                            db.upsert_source(cur, rec, "api")
                    conn.commit()
                    n_found += 1
                else:
                    n_miss += 1
                if k % 100 == 0:
                    log(f"  {k}/{len(oa)}  calls={client.calls} cache={client.cache_hits} "
                        f"found={n_found} miss={n_miss} skipped={n_skipped} quota_left={client.remaining}")
        except (QuotaExceeded, BudgetExhausted) as ex:
            conn.commit()
            log(f"stopped: {ex}")
            log(f"calls={client.calls} cache_hits={client.cache_hits} found={n_found} miss={n_miss}")
            sys.exit(3)
    if args.dry_run:
        log(f"dry run: up to {client.planned} API calls would be made "
            f"({client.cache_hits} already cached, {n_skipped} skipped)")
    else:
        log(f"done: calls={client.calls} cache_hits={client.cache_hits} found={n_found} "
            f"miss={n_miss} skipped={n_skipped} quota_left={client.remaining}")


# ============================================================= resolve =======

def _prep_oa(o):
    titles = [o["display_name"]] + list(o["alternate_titles"] or [])
    titles = [t for t in titles if t]
    forms, keys = [], set()
    for t in titles:
        forms.extend(fuzzy_forms(t))
        keys |= title_keys(t)
    issns = {norm_issn(x) for x in [o["issn_l_n"]] + list(o["issns_n"] or [])}
    issns.discard(None)
    return {**o, "titles": titles, "forms": forms, "keys": keys, "issns": issns,
            "pub": publisher_key(o["publisher"]), "first": o["first_publication_year"],
            "last": o["last_publication_year"], "country": o["country_code"]}


def _prep_sc(s):
    return {**s, "forms": fuzzy_forms(s["title"]), "keys": title_keys(s["title"]),
            "issns": {x for x in (s["issns"] or []) if x}, "pub": publisher_key(s["publisher"]),
            "country": None}


def _score(o, s, method, idf):
    tsim, ti = linkage.best_title_similarity(o["forms"], s["forms"], idf)
    score, ev = linkage.score_pair(o, s, tsim)
    ev.update({"oa_title": o["titles"][0], "scopus_title": s["title"],
               "matched_oa_form": " ".join(o["forms"][ti]) if ti >= 0 else None})
    tier = linkage.assign_tier(method, score, bool(ev["shared_issns"]))
    return score, tier, ev


def cmd_resolve(args):
    import numpy as np
    from rapidfuzz import fuzz, process
    rid = run_id()
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        oa = [_prep_oa(o) for o in db.load_oa_candidates(cur, args.min_works, args.active_since, args.limit)]
        sc = [_prep_sc(s) for s in db.load_scopus_sources(cur)]
    log(f"resolve {rid}: {len(oa)} OpenAlex journals x {len(sc)} Scopus sources")
    if not sc:
        raise SystemExit("no Scopus sources loaded: run `sourcelist` and/or `fetch` first")

    idf = linkage.build_idf([f for x in oa for f in x["forms"]] + [f for s in sc for f in s["forms"]])
    by_issn: dict[str, list[int]] = {}
    by_key: dict[str, list[int]] = {}
    for j, s in enumerate(sc):
        for i in s["issns"]:
            by_issn.setdefault(i, []).append(j)
        for k in s["keys"]:
            by_key.setdefault(k, []).append(j)

    pairs: dict[tuple[str, str], dict] = {}
    oa_has_t1: set[str] = set()

    def add(o, j, method):
        s = sc[j]
        key = (o["oa_source_id"], s["scopus_source_id"])
        if key in pairs:
            return
        score, tier, ev = _score(o, s, method, idf)
        if tier is None:
            return
        pairs[key] = {"oa_source_id": key[0], "scopus_source_id": key[1], "match_method": method,
                      "tier": tier, "score": score, "evidence": ev, "decided_by": "auto",
                      "is_best_for_oa": False, "is_best_for_scopus": False,
                      "_oa": o, "_sc": s}
        if tier == 1:
            oa_has_t1.add(key[0])

    # T1/T2: ISSN
    for o in oa:
        for i in o["issns"]:
            for j in by_issn.get(i, []):
                add(o, j, "issn_l" if o["issn_l_n"] in sc[j]["issns"] else "issn_any")
    n_issn = len(pairs)
    # T3: exact normalized title, only for journals without an accepted ISSN link
    for o in oa:
        if o["oa_source_id"] in oa_has_t1:
            continue
        for k in o["keys"]:
            for j in by_key.get(k, []):
                add(o, j, "title_exact")
    n_exact = len(pairs) - n_issn
    # T4: fuzzy title blocking with token_sort_ratio, then full scoring
    rest = [o for o in oa if o["oa_source_id"] not in oa_has_t1 and o["forms"]]
    if rest and not args.no_fuzzy:
        choices, choice_src = [], []
        for j, s in enumerate(sc):
            for f in s["forms"]:
                choices.append(" ".join(f))
                choice_src.append(j)
        queries, query_src = [], []
        for o in rest:
            for f in o["forms"][:4]:
                queries.append(" ".join(f))
                query_src.append(o)
        log(f"fuzzy blocking: {len(queries)} query strings x {len(choices)} Scopus strings")
        step = 500
        for start in range(0, len(queries), step):
            block = queries[start:start + step]
            m = process.cdist(block, choices, scorer=fuzz.token_sort_ratio,
                              score_cutoff=linkage.THRESH["fuzzy_block"], dtype=np.uint8, workers=-1)
            for r in range(m.shape[0]):
                nz = np.nonzero(m[r])[0]
                if len(nz) > linkage.THRESH["fuzzy_topk"]:
                    nz = nz[np.argsort(m[r][nz])[::-1][:linkage.THRESH["fuzzy_topk"]]]
                o = query_src[start + r]
                for c in nz:
                    add(o, choice_src[c], "title_fuzzy")
            if (start // step) % 20 == 0:
                log(f"  {min(start + step, len(queries))}/{len(queries)}")
    n_fuzzy = len(pairs) - n_issn - n_exact

    # overrides
    n_over = 0
    sc_ids = {s["scopus_source_id"]: s for s in sc}
    oa_ids = {o["oa_source_id"]: o for o in oa}
    if OVERRIDES.exists():
        with open(OVERRIDES, newline="") as f:
            for row in csv.DictReader(f):
                oid, sid = row["oa_source_id"].strip(), (row.get("scopus_source_id") or "").strip()
                dec = (row.get("decision") or "").strip().lower()
                who = row.get("reviewer") or "manual"
                if oid not in oa_ids:
                    continue
                if dec == "reject" and not sid:
                    for key, p in pairs.items():
                        if key[0] == oid:
                            p.update(tier=3, decided_by=who)
                    n_over += 1
                elif dec in ("accept", "reject") and sid in sc_ids:
                    key = (oid, sid)
                    if key not in pairs:
                        o, s = oa_ids[oid], sc_ids[sid]
                        score, _, ev = _score(o, s, "manual", idf)
                        pairs[key] = {"oa_source_id": oid, "scopus_source_id": sid, "score": score,
                                      "evidence": ev, "is_best_for_oa": False,
                                      "is_best_for_scopus": False, "_oa": o, "_sc": s,
                                      "match_method": "manual", "tier": 1, "decided_by": who}
                    pairs[key].update(tier=1 if dec == "accept" else 3, decided_by=who,
                                      match_method="manual")
                    n_over += 1

    # best flags among accepted rows
    def oa_rank(p):
        return (p["score"], len(p["evidence"].get("shared_issns", [])), p["_sc"]["coverage_end"] or 9999)

    def sc_rank(p):
        return (p["score"], p["_oa"]["works_count"] or 0)

    best_oa: dict[str, dict] = {}
    best_sc: dict[str, dict] = {}
    for p in pairs.values():
        if p["tier"] != 1:
            continue
        if p["oa_source_id"] not in best_oa or oa_rank(p) > oa_rank(best_oa[p["oa_source_id"]]):
            best_oa[p["oa_source_id"]] = p
        if p["scopus_source_id"] not in best_sc or sc_rank(p) > sc_rank(best_sc[p["scopus_source_id"]]):
            best_sc[p["scopus_source_id"]] = p
    for p in best_oa.values():
        p["is_best_for_oa"] = True
    for p in best_sc.values():
        p["is_best_for_scopus"] = True

    rows = [{k: v for k, v in p.items() if not k.startswith("_")} for p in pairs.values()]
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        db.write_map(cur, rows, rid)
        cur.execute("ANALYZE matching.oa_scopus_source_map")
        conn.commit()
        cur.execute("SELECT match_method, tier, count(*), count(DISTINCT oa_source_id) "
                    "FROM matching.oa_scopus_source_map GROUP BY 1, 2 ORDER BY 2, 1")
        summary = cur.fetchall()
    log(f"pairs generated: issn={n_issn} title_exact={n_exact} title_fuzzy={n_fuzzy} overrides={n_over}")
    log(f"OpenAlex journals with an accepted match: {len(best_oa)} / {len(oa)}")
    log(f"{'method':<14}{'tier':>5}{'pairs':>9}{'oa_journals':>13}")
    for m, t, n, d in summary:
        log(f"{m:<14}{t:>5}{n:>9}{d:>13}")


# ======================================================= review/export =======

_DETAIL_SQL = """
SELECT m.oa_source_id, c.display_name AS oa_title, c.issn_l_n AS oa_issn_l,
       array_to_string(c.issns_n, '|') AS oa_issns, c.publisher AS oa_publisher,
       c.first_publication_year AS oa_first_year, c.last_publication_year AS oa_last_year,
       c.works_count AS oa_works_count,
       m.scopus_source_id, s.title AS scopus_title,
       (SELECT string_agg(issn, '|') FROM scopus.source_issns i WHERE i.scopus_source_id = s.scopus_source_id) AS scopus_issns,
       s.publisher AS scopus_publisher, s.coverage_start, s.coverage_end, s.source_type, s.origin,
       (SELECT string_agg(asjc_code::text, '|' ORDER BY asjc_code) FROM scopus.source_asjc a WHERE a.scopus_source_id = s.scopus_source_id) AS asjc_codes,
       m.match_method, m.tier, m.score, m.is_best_for_oa, m.is_best_for_scopus,
       m.evidence->>'title_sim' AS title_sim, m.evidence->>'pub_sim' AS pub_sim,
       m.evidence->>'year_overlap' AS year_overlap, m.evidence->>'shared_issns' AS shared_issns,
       m.decided_by, m.run_id
FROM matching.oa_scopus_source_map m
JOIN matching.oa_journal_candidates c USING (oa_source_id)
JOIN scopus.sources s USING (scopus_source_id)
"""


def _write_csv(path: Path, cur):
    DATA.mkdir(exist_ok=True)
    cols = [d.name for d in cur.description]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        n = 0
        for row in cur:
            w.writerow(row)
            n += 1
    log(f"wrote {n} rows to {path}")


def cmd_review(args):
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute(_DETAIL_SQL + " WHERE m.tier = 2 ORDER BY c.works_count DESC, m.score DESC")
        _write_csv(DATA / "review_queue.csv", cur)


def cmd_export(args):
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT m.oa_source_id, m.scopus_source_id, m.match_method, m.score,
                   m.is_best_for_oa, m.is_best_for_scopus,
                   m.evidence->>'shared_issns' AS shared_issns,
                   s.coverage_start, s.coverage_end,
                   (SELECT string_agg(asjc_code::text, '|' ORDER BY asjc_code)
                    FROM scopus.source_asjc a WHERE a.scopus_source_id = s.scopus_source_id) AS asjc_codes,
                   m.decided_by, m.run_id
            FROM matching.oa_scopus_source_map m JOIN scopus.sources s USING (scopus_source_id)
            WHERE m.tier = 1 ORDER BY m.oa_source_id, m.score DESC""")
        _write_csv(DATA / "crosswalk.csv", cur)


# =============================================================== stats =======

def cmd_stats(args):
    y0, y1 = args.years
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        log("share of works in Scopus-covered journals, by year ...")
        cur.execute("""
            WITH cov AS (
              SELECT m.oa_source_id, min(s.coverage_start) AS cs,
                     CASE WHEN bool_or(s.coverage_end IS NULL) THEN NULL ELSE max(s.coverage_end) END AS ce
              FROM matching.oa_scopus_source_map m JOIN scopus.sources s USING (scopus_source_id)
              WHERE m.tier = 1 GROUP BY 1)
            SELECT w.publication_year, count(*) AS works,
                   count(*) FILTER (WHERE cov.oa_source_id IS NOT NULL) AS works_in_matched_journals,
                   count(*) FILTER (WHERE cov.oa_source_id IS NOT NULL
                        AND w.publication_year >= coalesce(cov.cs, 0)
                        AND w.publication_year <= coalesce(cov.ce, 9999)) AS works_in_scopus_coverage
            FROM openalex.works w LEFT JOIN cov ON cov.oa_source_id = w.primary_location_source_id
            WHERE w.publication_year BETWEEN %s AND %s
            GROUP BY 1 ORDER BY 1""", (y0, y1))
        _write_csv(DATA / "stats_coverage_by_year.csv", cur)

        log("works by ASJC area and year (fractional counting) ...")
        cur.execute("""
            WITH ja AS (
              SELECT DISTINCT oa_source_id, area_code FROM matching.oa_journal_asjc),
            jw AS (
              SELECT oa_source_id, area_code, 1.0 / count(*) OVER (PARTITION BY oa_source_id) AS w FROM ja)
            SELECT jw.area_code, regexp_replace(a.name, '^General ', '') AS area_name, w.publication_year,
                   round(sum(jw.w), 1) AS works_fractional, count(*) AS works_full
            FROM openalex.works w
            JOIN jw ON jw.oa_source_id = w.primary_location_source_id
            LEFT JOIN scopus.asjc a ON a.code = jw.area_code * 100
            WHERE w.publication_year BETWEEN %s AND %s
            GROUP BY 1, 2, 3 ORDER BY 1, 3""", (y0, y1))
        _write_csv(DATA / "stats_works_by_asjc_area.csv", cur)

        log("largest unmatched OpenAlex journals ...")
        cur.execute("""
            SELECT c.oa_source_id, c.display_name, c.issn_l_n, c.publisher, c.works_count,
                   c.first_publication_year, c.last_publication_year, c.is_in_doaj
            FROM matching.oa_journal_candidates c
            LEFT JOIN matching.oa_scopus_source_map m ON m.oa_source_id = c.oa_source_id AND m.tier = 1
            WHERE m.oa_source_id IS NULL ORDER BY c.works_count DESC LIMIT %s""", (args.top,))
        _write_csv(DATA / "stats_top_unmatched.csv", cur)


# ================================================================ eval =======

def cmd_eval_sample(args):
    rng = random.Random(args.seed)
    strata = {}
    with db.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute(_DETAIL_SQL + " WHERE m.tier IN (1, 2)")
        cols = [d.name for d in cur.description]
        for row in cur:
            r = dict(zip(cols, row))
            strata.setdefault(f"tier{r['tier']}_{r['match_method']}", []).append(r)
        cur.execute("""
            SELECT c.oa_source_id, c.display_name AS oa_title, c.issn_l_n AS oa_issn_l,
                   array_to_string(c.issns_n, '|') AS oa_issns, c.publisher AS oa_publisher,
                   c.first_publication_year AS oa_first_year, c.last_publication_year AS oa_last_year,
                   c.works_count AS oa_works_count
            FROM matching.oa_journal_candidates c
            LEFT JOIN matching.oa_scopus_source_map m ON m.oa_source_id = c.oa_source_id
            WHERE m.oa_source_id IS NULL AND c.works_count >= %s""", (args.min_works,))
        ucols = [d.name for d in cur.description]
        strata["unmatched"] = [dict(zip(ucols, row)) for row in cur]
    out = []
    for name, rows in sorted(strata.items()):
        pick = rng.sample(rows, min(args.n, len(rows)))
        for r in pick:
            out.append({"stratum": name, **{k: r.get(k) for k in cols},
                        "gold_scopus_source_id": "", "coder": "", "note": ""})
    DATA.mkdir(exist_ok=True)
    path = DATA / f"eval_sample_seed{args.seed}.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()) if out else ["stratum"])
        w.writeheader()
        w.writerows(out)
    log(f"wrote {len(out)} rows across {len(strata)} strata to {path}")


def _wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def cmd_eval_score(args):
    with open(args.file, newline="") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("coder") or "").strip()]
    if not rows:
        raise SystemExit("no coded rows (fill in `coder` and `gold_scopus_source_id`)")
    by = {}
    fn = 0
    for r in rows:
        gold = (r.get("gold_scopus_source_id") or "").strip()
        st = r["stratum"]
        if st == "unmatched":
            fn += bool(gold)
            continue
        ok = gold == (r.get("scopus_source_id") or "").strip()
        k, n = by.get(st, (0, 0))
        by[st] = (k + ok, n + 1)
    print(f"{'stratum':<24}{'n':>5}{'precision':>11}{'wilson95':>18}")
    for st, (k, n) in sorted(by.items()):
        lo, hi = _wilson(k, n)
        print(f"{st:<24}{n:>5}{k / n:>11.3f}{f'[{lo:.2f}, {hi:.2f}]':>18}")
    n_un = sum(r["stratum"] == "unmatched" for r in rows)
    if n_un:
        print(f"unmatched stratum: {fn}/{n_un} coded as actually in Scopus (recall loss)")


# ================================================================ main =======

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", help="psycopg DSN (default: $OPENALEX_DSN or dbname=openalex user=simone host=localhost)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("schema", help="create scopus/matching schemas, refresh candidate view")
    p.add_argument("--no-refresh", action="store_true")
    p.set_defaults(fn=cmd_schema)

    p = sub.add_parser("sourcelist", help="load the Scopus Source List xlsx")
    p.add_argument("--file", help="path to ext_list_*.xlsx (default: download into cache/)")
    p.set_defaults(fn=cmd_sourcelist)

    p = sub.add_parser("fetch", help="query the Serial Title API (cached, quota-aware)")
    p.add_argument("--mode", choices=["issn", "title", "both"], default="both")
    p.add_argument("--min-works", type=int, default=50)
    p.add_argument("--active-since", type=int, default=None, help="require last_publication_year >= this")
    p.add_argument("--limit", type=int, default=None, help="only the top-N candidates by works_count")
    p.add_argument("--max-calls", type=int, default=None, help="hard cap on network calls this run")
    p.add_argument("--reserve", type=int, default=50, help="stop when quota remaining <= this")
    p.add_argument("--count", type=int, default=10, help="results per title search")
    p.add_argument("--view", default="STANDARD", choices=["STANDARD", "ENHANCED", "CITESCORE"])
    p.add_argument("--skip-known-any", action="store_true",
                   help="also skip journals whose ISSN is known from the Source List (default: only API-known)")
    p.add_argument("--refetch", action="store_true", help="ignore the looked-up log (cache still applies)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_fetch)

    p = sub.add_parser("resolve", help="score candidates and write the crosswalk")
    p.add_argument("--min-works", type=int, default=0)
    p.add_argument("--active-since", type=int, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--no-fuzzy", action="store_true", help="skip the fuzzy-title tier")
    p.set_defaults(fn=cmd_resolve)

    sub.add_parser("review", help="export tier-2 pairs to data/review_queue.csv").set_defaults(fn=cmd_review)
    sub.add_parser("export", help="export accepted pairs to data/crosswalk.csv").set_defaults(fn=cmd_export)

    p = sub.add_parser("stats", help="coverage statistics (scans works for the year range)")
    p.add_argument("--years", type=int, nargs=2, default=[2015, 2025], metavar=("FROM", "TO"))
    p.add_argument("--top", type=int, default=100)
    p.set_defaults(fn=cmd_stats)

    p = sub.add_parser("eval-sample", help="stratified sample for manual coding")
    p.add_argument("--seed", type=int, default=20260903)
    p.add_argument("--n", type=int, default=60, help="rows per stratum")
    p.add_argument("--min-works", type=int, default=50, help="for the unmatched stratum")
    p.set_defaults(fn=cmd_eval_sample)

    p = sub.add_parser("eval-score", help="precision per stratum from a coded sample")
    p.add_argument("file")
    p.set_defaults(fn=cmd_eval_score)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
