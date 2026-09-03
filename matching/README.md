# matching/ — OpenAlex ↔ Scopus journal crosswalk

Matches OpenAlex journals (the `sources` table of the loaded snapshot) to
Scopus sources so that journals — and, through `works.primary_location_source_id`,
their articles — can be sampled by Scopus metadata, above all the ASJC
discipline codes. Scopus data comes from Elsevier's developer platform
(<https://dev.elsevier.com/>), specifically the **Serial Title API**, plus the
free monthly **Scopus Source List** spreadsheet.

## Design in brief

- **Identifiers first, names last.** ISSN-L → any ISSN → exact normalized
  title → fuzzy title → human review. Title tiers never add a second Scopus
  link to a journal that already has an ISSN link.
- **One additive score** (`linkage.py`) combines ISSN agreement, an
  IDF-weighted, order-aware title similarity, publisher agreement,
  coverage-year overlap and country. Hard rules stop the classic traps:
  *Physical Review A* vs *B*, *Journal* vs *Journal Letters*, supplements,
  reused ISSNs.
- **Time-bounded crosswalk.** Scopus coverage years are stored per pair;
  sampling joins on `publication_year` within coverage, not on membership alone.
- **Many-to-many stored, one-to-one available.** Scopus creates a new
  source-id on every title change while OpenAlex keeps one record, so one OA
  journal may legitimately map to two Scopus ids. All scored pairs are stored
  with `is_best_for_oa` / `is_best_for_scopus` flags.
- **Every API response is cached** (SQLite, gitignored). Re-runs cost no quota.
- **ASJC multi-assignment** is kept in full; coverage stats use fractional
  counting (1/k per code), and Scopus has no "primary" code — never use the first.

## How the design was produced: the panel

The code was designed by a panel of six specialist reviewers (run as parallel
agents on 2026-09-03), each writing a memo against the same brief: the loaded
`openalex.sources` table, the Serial Title API, and the goal of sampling
journals and articles by Scopus discipline. The memos were then reconciled
into one design and the result was calibrated on real data (below).

| reviewer | main recommendations, and where they landed |
|---|---|
| **API integration** | Read the WADL, the views page, the quota page and the Elsevier API guide; probed `api.elsevier.com` live and downloaded the Source List. Established: ISSN lookup accepts print or e-ISSN with or without hyphen and answers 404 for unknown ISSNs; `title=` is an anywhere-substring search with no wildcards; there is no lookup by source-id; quota is 20,000/week at 6/s with `X-RateLimit-*` headers and a 429 `QUOTA_EXCEEDED` status; unentitled keys get a minimal record without ASJC or metrics; the Source List is a public xlsx with 8-character ISSNs, ASJC codes, coverage ranges and no metrics. All of this is encoded in `scopus_client.py` and `match.py sourcelist`. |
| **Science of science** | Match on ISSN, never on title alone; expect one OpenAlex record to map to several Scopus ids because Scopus opens a new source on every title change; record coverage years per pair and sample works by year within coverage; keep all ASJC codes and use fractional counting, never "the first code"; scope candidates to `type = 'journal'`, order by `works_count` so quota exhaustion hits the tail; report coverage as the share of *works*, by year, field, country and OA status. Adopted in full: the crosswalk is many-to-many with coverage years, `stats` produces the tables, the API walk is ordered by `works_count`. |
| **Computational social science** | Cache every raw response keyed by query before parsing it; make runs idempotent and resumable with the cache as the only checkpoint; a hard `--max-calls` budget, a quota reserve and a dry run; a review queue CSV with the evidence a reviewer needs and a hand-maintained overrides file applied last; a fixed-seed stratified evaluation sample with Wilson intervals; commit only identifier-level outputs because Scopus content cannot be redistributed. Adopted in full (`cache/`, `overrides.csv`, `review`, `eval-sample`, `eval-score`, the Terms of use section). |
| **Database / SQL** | Separate `scopus` and `matching` schemas so a Scopus re-pull cannot touch the snapshot; normalized ISSNs in a materialized view over `openalex.sources` rather than a column on the loader's table; a crosswalk table with method, tier, score, evidence jsonb and best-flags; a view of OpenAlex ISSN duplicates; sample works through the already-indexed `works.primary_location_source_id`. Adopted, with one deviation: the memo suggested doing fuzzy title blocking inside Postgres with `pg_trgm`; the resolver does it in Python with `rapidfuzz` instead, so that the normalization and the scoring live in one place and need no extensions. |
| **Record linkage** | A cascade of tiers with one additive log-odds score: shared ISSNs +4/+6, title similarity scaled above 0.85, publisher agreement, coverage-year overlap, country, and penalties for section letters, "Letters", supplements and reused ISSNs; title tiers must never add a second link where an ISSN link exists; at most two API calls per journal; skip generic titles; store all pairs above a review floor with best-flags on both sides; a stratified gold set with Wilson intervals per tier. Adopted as `linkage.py`. The initial weights were the memo's; two thresholds were tightened after the real-data pass (below). |
| **NLP** | A deterministic key (NFKD, casefold, `&` to `and`, medium qualifiers dropped, `Title, The` un-inverted, parallel titles split, `Part II` to `2`, a short unambiguous abbreviation dictionary, leading articles stripped in six languages) and a separate fuzzy form that keeps section letters; an IDF-weighted soft Jaccard with typo alignment and prefix alignment for abbreviations; asymmetric-presence penalties for section, content-type and scope tokens; Cyrillic transliteration, no cross-script fuzzy matching; 25 key tests and 11 must-not-match pairs. Adopted as `normalize.py` and the similarity in `linkage.py`; the tests are in the modules. |

### Calibration on real data

The first full run (Source List only, 226,534 OpenAlex journals against
48,888 Scopus sources) accepted 47,880 journals. Sampling the accepted
fuzzy-title pairs showed four failure modes the memos had not anticipated,
each fixed and turned into a test:

1. **Jaro-Winkler aligned different words.** Its prefix bonus scored
   *hydroecology* ~ *hydrology*, *Biomics* ~ *Biomimetics* and
   *Pontica* ~ *Phonetica* above 0.92. Token alignment now uses normalized
   Levenshtein at 0.85 on tokens of five or more letters, which keeps real
   typos (*Phillippine*) and inflections (*sciences*) and drops those.
2. **Bag-of-words ignores order.** *Journal of Education Science* scored 1.0
   against *Journal of Science Education*. Twenty percent of the title score
   now depends on the longest common token subsequence.
3. **Title plus year overlap was enough to accept** even when both sides had
   ISSNs that disagreed. The ISSN-conflict penalty rose to -2 and the
   title-tier acceptance threshold to 5, so a title match needs publisher
   agreement and year overlap, and no ISSN conflict, to be accepted.
4. **One shared ISSN with a dissimilar title was accepted.** ISSN-tier
   acceptance rose to 3.5, so a single ISSN hit needs title similarity of at
   least 0.6 or a matching publisher; otherwise it goes to review.

After recalibration the same run accepts 43,736 OpenAlex journals
(39,389 on ISSN-L, 575 on another ISSN, 3,812 on exact title, 19 on fuzzy
title) covering 40,697 distinct Scopus sources, with 4,736 journals in the
review queue. The 2,747 fuzzy acceptances that disappeared were almost all
of the kinds listed above. These figures are from the Source List alone; the
API adds source-ids for the ~10K serials the list omits and the metrics.

Two normalization gaps surfaced at the same time: Scopus country
qualifiers such as *Sustainability (Switzerland)* and parallel titles joined
by a period (*South African dental journal. Suid Afrikaanse tandheelkundige
tydskrif*). Parentheticals are now treated as subtitle material with reduced
weight, and period-joined parallel titles are split.

## Files

| file | role |
|---|---|
| `match.py` | CLI: `schema · sourcelist · fetch · resolve · review · export · stats · eval-sample · eval-score` |
| `sql/01_scopus_schema.sql` | schemas `scopus` (Scopus data) and `matching` (candidates view, crosswalk) |
| `normalize.py` | ISSN check-digit validation, title keys, fuzzy token forms, publisher keys (`--test`) |
| `linkage.py` | pair scoring, weights `W`, thresholds `THRESH`, tier assignment (`--test`) |
| `scopus_client.py` | Serial Title API client, rate limiting, SQLite cache, entry parser (`--test`) |
| `db.py` | psycopg 3 helpers: upserts and loaders |
| `overrides.csv` | hand decisions applied last by `resolve` (committed) |
| `data/` | generated CSVs (gitignored): `crosswalk.csv`, `review_queue.csv`, `stats_*.csv`, `eval_sample_*.csv` |
| `cache/` | raw API responses + downloaded Source List (gitignored; **never commit**) |

## Setup

```bash
pip install --user httpx pandas "psycopg[binary]" rapidfuzz python-dotenv openpyxl
```

Secrets go in the repo-root `.env` (already gitignored):

```
ELSEVIER_API_KEY=...        # https://dev.elsevier.com/apikey/manage
ELSEVIER_INSTTOKEN=...      # optional; off-campus institutional access
```

Postgres: the loaded `openalex` database, reached as `dbname=openalex
user=simone host=localhost` via `~/.pgpass`, or set `OPENALEX_DSN`.

## Run

```bash
cd matching
python match.py schema                      # once; and after every snapshot reload
python match.py sourcelist                  # free bulk list: ~49K sources with ISSN + ASJC + coverage
python match.py fetch --dry-run --limit 5000    # how many API calls would be spent
python match.py fetch --min-works 50 --max-calls 15000   # ISSN lookups, then title search; resumable
python match.py resolve                     # cascade -> matching.oa_scopus_source_map
python match.py review                      # data/review_queue.csv for a human
python match.py export                      # data/crosswalk.csv (identifiers only)
python match.py stats --years 2015 2025     # coverage tables (scans works; minutes)
```

`fetch` walks candidates by `works_count` descending so an exhausted quota
hits the tail, not the head. Per journal it spends at most two ISSN lookups
(ISSN-L, then one more ISSN) and, only if both miss, at most two title
searches (display name, then a sufficiently different alternate title).
Generic titles ("Bulletin", "Proceedings", …) are never searched. Journals
whose ISSN is already known from the API are skipped; add `--skip-known-any`
to also skip those known only from the Source List (you then lose the API's
metrics for them). Exit code 3 means the quota or `--max-calls` was hit; run
again later and it resumes.

The Serial Title API quota is 20,000 requests/week at 6/s. Institutional
entitlement decides how much of each record you see; without it the API
returns a minimal record (no ASJC, no metrics). The Source List needs no key
and already carries ASJC codes, so run `sourcelist` first: for most journals
the API then only adds source-ids, CiteScore/SNIP/SJR and the ~10K serials the
list omits.

## Reading the crosswalk

`matching.oa_scopus_source_map`:

| column | meaning |
|---|---|
| `match_method` | `issn_l`, `issn_any`, `title_exact`, `title_fuzzy`, `manual` |
| `tier` | 1 accept, 2 review, 3 rejected by hand |
| `score` | additive score; thresholds in `linkage.THRESH` |
| `is_best_for_oa` / `is_best_for_scopus` | highest-scoring accepted partner on each side |
| `evidence` | jsonb: `shared_issns`, `title_sim`, `pub_sim`, `year_overlap`, flags |

`matching.oa_journal_asjc` is the join target for sampling:

```sql
-- works in journals classified 1405 (Management of Technology and Innovation), 2015-2024
SELECT w.id, w.publication_year, w.primary_location_source_id
FROM openalex.works w
JOIN (SELECT DISTINCT oa_source_id, coverage_start, coverage_end
      FROM matching.oa_journal_asjc WHERE asjc_code = 1405) j
  ON j.oa_source_id = w.primary_location_source_id
WHERE w.publication_year BETWEEN 2015 AND 2024
  AND w.publication_year BETWEEN coalesce(j.coverage_start, 0) AND coalesce(j.coverage_end, 9999);
```

Journals have several ASJC codes (median 2). For descriptive statistics weight
each journal 1/k per code; for sampling by discipline take the full set of
journals carrying the code and keep the whole code list for post-stratification
(e.g. excluding 1000 *Multidisciplinary*).

## Review loop

`review` writes one row per tier-2 pair with the evidence a reviewer needs.
Record decisions in `overrides.csv`:

```
oa_source_id,scopus_source_id,decision,reviewer,date,note
https://openalex.org/S123,21100,accept,ss,2026-09-03,title change 2014
https://openalex.org/S456,,reject,ss,2026-09-03,repository mislabelled as journal
```

`accept` forces tier 1 (`match_method = manual`); `reject` with a Scopus id
forces tier 3 for that pair; `reject` with an empty Scopus id blocks every
automatic pair for that journal. `resolve` re-applies the file on every run.

## Evaluation

```bash
python match.py eval-sample --seed 20260903 --n 60   # per stratum: tier1 by method, tier2, unmatched
python match.py eval-score data/eval_sample_seed20260903.csv
```

Fill `gold_scopus_source_id` and `coder` (leave gold empty for "not in Scopus").
`eval-score` reports precision per stratum with Wilson 95% intervals and how many
"unmatched" journals were actually in Scopus. Two coders and a Cohen's κ are
the expected standard; refit `linkage.W` on the coded set once it exists.

## Terms of use

Serial Title API responses are Scopus content. The cache stays on this
machine; do not commit it or share it. `crosswalk.csv` deliberately contains
identifiers, method, score, coverage years and ASJC codes only. Titles,
publishers and metrics remain in the database. This is a cautious reading of
Elsevier's API terms for personal research use, not legal advice.

## Not done yet

- Real-data check of the API client: written against the WADL and Elsevier's
  documented example response, not yet exercised with a key.
- Gold-standard coding and weight refit (`linkage.W` are panel starting points).
- `merged_ids` / deleted sources are not tracked; refreshes are full reruns.
