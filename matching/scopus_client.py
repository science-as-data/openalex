"""Thin client for the Scopus Serial Title API with an on-disk response cache.

Endpoints (https://dev.elsevier.com/documentation/SerialTitleAPI.wadl):
    GET /content/serial/title/issn/{issn}      one serial by print or e-ISSN
    GET /content/serial/title?title=...        substring title search

Quota for this API: 20,000 requests per week, 6 per second. Every response
with status 200 or 404 is cached in a SQLite file keyed by the query, so a
re-run never spends quota. 429 with X-ELS-Status QUOTA_EXCEEDED aborts.

Secrets come from the environment (or the repo-root .env):
    ELSEVIER_API_KEY     required
    ELSEVIER_INSTTOKEN   optional, for off-campus institutional access

Run ``python scopus_client.py --test`` to exercise the entry parser offline.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from normalize import norm_issn

BASE = "https://api.elsevier.com/content/serial/title"
HERE = Path(__file__).resolve().parent
DEFAULT_CACHE = HERE / "cache" / "scopus_api.sqlite"


class QuotaExceeded(RuntimeError):
    pass


class BudgetExhausted(RuntimeError):
    pass


@dataclass
class Response:
    request_key: str
    status: int
    body: dict
    from_cache: bool
    remaining: int | None = None
    reset: int | None = None

    @property
    def entries(self) -> list[dict]:
        """Serial records in the response; [] for 404 / empty result sets."""
        if self.status != 200:
            return []
        ents = (self.body.get("serial-metadata-response") or {}).get("entry") or []
        return [e for e in ents if isinstance(e, dict) and "error" not in e]


class Cache:
    def __init__(self, path: Path = DEFAULT_CACHE):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS responses (
                request_key TEXT PRIMARY KEY, kind TEXT, query TEXT, url TEXT,
                params TEXT, http_status INTEGER, fetched_at TEXT,
                rate_remaining INTEGER, rate_reset INTEGER, els_status TEXT,
                body TEXT);
            CREATE TABLE IF NOT EXISTS lookups (
                oa_source_id TEXT, request_key TEXT, fetched_at TEXT,
                PRIMARY KEY (oa_source_id, request_key));
        """)

    def get(self, key: str) -> Response | None:
        row = self.db.execute(
            "SELECT http_status, body, rate_remaining, rate_reset FROM responses WHERE request_key=?",
            (key,)).fetchone()
        if not row:
            return None
        body = json.loads(row[1]) if row[1] else {}
        return Response(key, row[0], body, True, row[2], row[3])

    def put(self, key, kind, query, url, params, status, text, remaining, reset, els_status):
        self.db.execute(
            "INSERT OR REPLACE INTO responses VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (key, kind, query, url, json.dumps(params, sort_keys=True), status,
             datetime.now(timezone.utc).isoformat(timespec="seconds"),
             remaining, reset, els_status, text))
        self.db.commit()

    def record_lookup(self, oa_source_id: str, key: str):
        self.db.execute("INSERT OR IGNORE INTO lookups VALUES (?,?,?)",
                        (oa_source_id, key, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.db.commit()

    def looked_up(self) -> set[str]:
        return {r[0] for r in self.db.execute("SELECT DISTINCT oa_source_id FROM lookups")}

    def stats(self) -> dict:
        rows = self.db.execute(
            "SELECT kind, http_status, count(*) FROM responses GROUP BY 1,2").fetchall()
        return {f"{k}:{s}": n for k, s, n in rows}


class ScopusClient:
    def __init__(self, api_key: str | None = None, insttoken: str | None = None,
                 cache: Cache | None = None, rate_per_sec: float = 6.0,
                 reserve: int = 50, max_calls: int | None = None,
                 view: str = "STANDARD", dry_run: bool = False):
        self.api_key = api_key or os.environ.get("ELSEVIER_API_KEY")
        self.insttoken = insttoken or os.environ.get("ELSEVIER_INSTTOKEN")
        self.cache = cache or Cache()
        self.min_interval = 1.0 / rate_per_sec
        self.reserve = reserve
        self.max_calls = max_calls
        self.view = view
        self.dry_run = dry_run
        self.calls = 0          # network calls this run
        self.cache_hits = 0
        self.planned = 0        # calls that would have been made in dry-run
        self.remaining: int | None = None
        self.reset: int | None = None
        self._last = 0.0
        headers = {"Accept": "application/json", "User-Agent": "openalex-matching/0.1"}
        if self.api_key:
            headers["X-ELS-APIKey"] = self.api_key
        if self.insttoken:
            headers["X-ELS-Insttoken"] = self.insttoken
        self.http = httpx.Client(headers=headers, timeout=30.0)

    # ---------------------------------------------------------------- calls

    def issn_lookup(self, issn: str) -> Response:
        v = norm_issn(issn, validate=False)
        if not v:
            raise ValueError(f"not an ISSN: {issn!r}")
        key = f"issn:{self.view}:{v}"
        return self._get(key, "issn", v, f"{BASE}/issn/{v}", {"view": self.view})

    def title_search(self, title: str, count: int = 10) -> Response:
        q = re.sub(r"\s+", " ", title).strip()
        key = f"title:{self.view}:{count}:{q.lower()}"
        return self._get(key, "title", q, BASE,
                         {"title": q, "count": count, "view": self.view})

    def _get(self, key, kind, query, url, params) -> Response:
        hit = self.cache.get(key)
        if hit:
            self.cache_hits += 1
            return hit
        if self.dry_run:
            self.planned += 1
            return Response(key, 0, {}, False)
        if not self.api_key:
            raise RuntimeError("ELSEVIER_API_KEY is not set (put it in the repo-root .env)")
        if self.max_calls is not None and self.calls >= self.max_calls:
            raise BudgetExhausted(f"--max-calls {self.max_calls} reached")
        if self.remaining is not None and self.remaining <= self.reserve:
            raise QuotaExceeded(f"quota remaining {self.remaining} <= reserve {self.reserve}")

        for attempt in range(4):
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            r = self.http.get(url, params=params)
            self.calls += 1
            els = r.headers.get("X-ELS-Status", "")
            rem = r.headers.get("X-RateLimit-Remaining")
            rst = r.headers.get("X-RateLimit-Reset")
            if rem is not None:
                self.remaining = int(rem)
            if rst is not None:
                self.reset = int(rst)
            if r.status_code == 429:
                if "QUOTA" in els.upper():
                    raise QuotaExceeded(f"quota exceeded; resets at {self.reset}")
                time.sleep(1.0 + attempt)          # per-second throttle
                continue
            if r.status_code >= 500:
                time.sleep(2.0 * (attempt + 1))
                continue
            if r.status_code in (401, 403):
                raise RuntimeError(f"HTTP {r.status_code} {els}: check ELSEVIER_API_KEY / entitlement")
            if r.status_code in (200, 404):
                try:
                    body = r.json()
                except ValueError:
                    body = {}
                self.cache.put(key, kind, query, url, params, r.status_code, r.text,
                               self.remaining, self.reset, els)
                return Response(key, r.status_code, body, False, self.remaining, self.reset)
            raise RuntimeError(f"HTTP {r.status_code} {els} for {url} {params}: {r.text[:300]}")
        raise RuntimeError(f"gave up after retries: {url} {params}")


# ------------------------------------------------------------ parsing -------

_SRC_ID = re.compile(r"sourceId=(\d+)")


def _int(x):
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return None


def _num(x):
    try:
        return float(str(x).strip())
    except (TypeError, ValueError):
        return None


def parse_entry(e: dict) -> dict | None:
    """Flatten one serial-metadata entry into the scopus.* row shapes."""
    sid = e.get("source-id")
    if not sid:
        for link in e.get("link") or []:
            m = _SRC_ID.search(str(link.get("@href", "")))
            if link.get("@ref") == "scopus-source" and m:
                sid = m.group(1)
    title = e.get("dc:title")
    if not sid or not title:
        return None
    issns = []
    for fld, kind in (("prism:issn", "print"), ("prism:eIssn", "electronic")):
        for raw in str(e.get(fld) or "").split(","):
            v = norm_issn(raw)
            if v:
                issns.append((v, kind))
    asjc = []
    for sa in e.get("subject-area") or []:
        code = _int(sa.get("@code"))
        if code:
            asjc.append((code, sa.get("@abbrev"), sa.get("$")))
    metrics: dict[int, dict] = {}
    for lst, key, col in (("SNIPList", "SNIP", "snip"), ("SJRList", "SJR", "sjr")):
        for m in ((e.get(lst) or {}).get(key) or []):
            y = _int(m.get("@year"))
            if y:
                metrics.setdefault(y, {})[col] = _num(m.get("$"))
    cs = e.get("citeScoreYearInfoList") or {}
    y = _int(cs.get("citeScoreCurrentMetricYear"))
    if y:
        metrics.setdefault(y, {})["citescore"] = _num(cs.get("citeScoreCurrentMetric"))
    for info in cs.get("citeScoreYearInfo") or []:        # view=CITESCORE
        y = _int(info.get("@year"))
        try:
            v = info["citeScoreInformationList"][0]["citeScoreInfo"][0]["citeScore"]
        except (KeyError, IndexError, TypeError):
            v = None
        if y and v is not None:
            metrics.setdefault(y, {})["citescore"] = _num(v)
    end = _int(e.get("coverageEndYear"))
    return {
        "scopus_source_id": str(sid),
        "title": title,
        "publisher": e.get("dc:publisher"),
        "source_type": e.get("prism:aggregationType"),
        "coverage_start": _int(e.get("coverageStartYear")),
        "coverage_end": end,
        "coverage_text": None,
        "is_active": (end is None or end >= datetime.now().year - 1) if e.get("coverageStartYear") else None,
        "oa_status": e.get("openaccessType"),
        "issns": sorted(set(issns)),
        "asjc": asjc,
        "metrics": metrics,
        "raw": e,
    }


# --------------------------------------------------------------- tests ------

_SAMPLE = {"serial-metadata-response": {"entry": [{
    "dc:title": "Food Chemistry", "dc:publisher": "Elsevier Ltd.",
    "coverageStartYear": "1976", "coverageEndYear": "2023",
    "prism:aggregationType": "journal", "source-id": "24039",
    "prism:issn": "0308-8146", "prism:eIssn": "1873-7072",
    "openaccess": "0", "openaccessType": "None",
    "subject-area": [{"@_fa": "true", "@code": "1602", "@abbrev": "CHEM", "$": "Analytical Chemistry"},
                     {"@_fa": "true", "@code": "1106", "@abbrev": "AGRI", "$": "Food Science"}],
    "SNIPList": {"SNIP": [{"@_fa": "true", "@year": "2022", "$": "2.197"}]},
    "SJRList": {"SJR": [{"@_fa": "true", "@year": "2022", "$": "1.624"}]},
    "citeScoreYearInfoList": {"citeScoreCurrentMetric": "14.9", "citeScoreCurrentMetricYear": "2022",
                              "citeScoreTracker": "12.6", "citeScoreTrackerYear": "2023"},
    "link": [{"@ref": "scopus-source", "@href": "https://www.scopus.com/source/sourceInfo.url?sourceId=24039"}],
}]}}


def _run_tests() -> int:
    r = Response("k", 200, _SAMPLE, False)
    assert len(r.entries) == 1
    p = parse_entry(r.entries[0])
    assert p["scopus_source_id"] == "24039", p
    assert p["issns"] == [("03088146", "print"), ("18737072", "electronic")], p["issns"]
    assert [a[0] for a in p["asjc"]] == [1602, 1106]
    assert p["metrics"] == {2022: {"snip": 2.197, "sjr": 1.624, "citescore": 14.9}}, p["metrics"]
    assert p["coverage_start"] == 1976 and p["coverage_end"] == 2023
    basic = {"dc:title": "X", "link": [{"@ref": "scopus-source", "@href": "…sourceInfo.url?sourceId=22199"}]}
    assert parse_entry(basic)["scopus_source_id"] == "22199"
    assert Response("k", 404, {"service-error": {}}, False).entries == []
    assert Response("k", 200, {"serial-metadata-response": {"entry": [{"error": "Result set was empty"}]}}, False).entries == []
    print("scopus_client: all tests passed")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.exit(_run_tests())
    print(__doc__)
