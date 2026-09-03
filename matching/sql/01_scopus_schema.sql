-- Scopus source metadata + the OpenAlex <-> Scopus journal crosswalk.
--
-- Two schemas next to the loaded `openalex` schema:
--   scopus   - Scopus sources as retrieved (Serial Title API or Source List xlsx)
--   matching - derived objects: normalized OpenAlex candidates + the crosswalk
--
-- Apply with:  python matching/match.py schema      (idempotent)
-- Everything here is additive; nothing in schema `openalex` is touched.

CREATE SCHEMA IF NOT EXISTS scopus;
CREATE SCHEMA IF NOT EXISTS matching;

-- ---------------------------------------------------------------- scopus ----

-- All Science Journal Classification: ~330 four-digit codes, 27 two-digit areas.
CREATE TABLE IF NOT EXISTS scopus.asjc (
    code       integer PRIMARY KEY,
    abbrev     text,
    name       text,
    area_code  integer GENERATED ALWAYS AS (code / 100) STORED
);

-- One row per Scopus source-id. `origin` records where the row came from:
-- 'api' (Serial Title API, richest) or 'sourcelist' (bulk xlsx). API rows are
-- never overwritten by a Source List reload.
CREATE TABLE IF NOT EXISTS scopus.sources (
    scopus_source_id text PRIMARY KEY,
    title            text NOT NULL,
    publisher        text,
    source_type      text,        -- journal | tradejournal | conferenceproceeding | bookseries
    coverage_start   integer,
    coverage_end     integer,     -- NULL = still covered
    coverage_text    text,        -- raw Source List string, e.g. '2019-2024; 2016-2017'
    is_active        boolean,
    oa_status        text,
    origin           text NOT NULL CHECK (origin IN ('api', 'sourcelist')),
    raw              jsonb,
    fetched_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scopus.source_issns (
    scopus_source_id text NOT NULL REFERENCES scopus.sources ON DELETE CASCADE,
    issn             text NOT NULL CHECK (issn ~ '^[0-9]{7}[0-9X]$'),   -- 8 chars, no hyphen
    kind             text NOT NULL CHECK (kind IN ('print', 'electronic')),
    PRIMARY KEY (scopus_source_id, issn)
);
CREATE INDEX IF NOT EXISTS source_issns_issn_idx ON scopus.source_issns (issn);

CREATE TABLE IF NOT EXISTS scopus.source_asjc (
    scopus_source_id text NOT NULL REFERENCES scopus.sources ON DELETE CASCADE,
    asjc_code        integer NOT NULL,
    PRIMARY KEY (scopus_source_id, asjc_code)
);
CREATE INDEX IF NOT EXISTS source_asjc_code_idx ON scopus.source_asjc (asjc_code);

-- Yearly metrics; API only (the Source List carries none).
CREATE TABLE IF NOT EXISTS scopus.source_metrics (
    scopus_source_id text NOT NULL REFERENCES scopus.sources ON DELETE CASCADE,
    year             integer NOT NULL,
    citescore        numeric,
    snip             numeric,
    sjr              numeric,
    PRIMARY KEY (scopus_source_id, year)
);

-- -------------------------------------------------------------- matching ----

CREATE OR REPLACE FUNCTION matching.norm_issn(text) RETURNS text
LANGUAGE sql IMMUTABLE AS
$$ SELECT nullif(regexp_replace(upper($1), '[^0-9X]', '', 'g'), '') $$;

-- OpenAlex journals worth matching, with ISSNs normalized once. Refresh after
-- every snapshot reload:  REFRESH MATERIALIZED VIEW matching.oa_journal_candidates;
CREATE MATERIALIZED VIEW IF NOT EXISTS matching.oa_journal_candidates AS
SELECT s.id                                  AS oa_source_id,
       s.display_name,
       coalesce(s.alternate_titles, '[]'::jsonb) AS alternate_titles,
       s.host_organization_name              AS publisher,
       s.country_code,
       s.works_count,
       s.first_publication_year,
       s.last_publication_year,
       s.is_in_doaj,
       matching.norm_issn(s.issn_l)          AS issn_l_n,
       ARRAY(SELECT DISTINCT matching.norm_issn(x)
             FROM jsonb_array_elements_text(coalesce(s.issn, '[]'::jsonb)) x
             WHERE matching.norm_issn(x) IS NOT NULL)  AS issns_n
FROM openalex.sources s
WHERE s.type = 'journal'
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS oa_journal_candidates_id_idx
    ON matching.oa_journal_candidates (oa_source_id);
CREATE INDEX IF NOT EXISTS oa_journal_candidates_works_idx
    ON matching.oa_journal_candidates (works_count DESC);
CREATE INDEX IF NOT EXISTS oa_journal_candidates_issns_idx
    ON matching.oa_journal_candidates USING gin (issns_n);

-- OpenAlex duplicates: several OA sources sharing one ISSN. First id = canonical.
CREATE OR REPLACE VIEW matching.oa_issn_duplicates AS
SELECT i AS issn,
       array_agg(oa_source_id ORDER BY works_count DESC) AS oa_source_ids,
       count(*) AS n
FROM matching.oa_journal_candidates, unnest(issns_n) AS i
GROUP BY i
HAVING count(*) > 1;

-- The crosswalk. Many-to-many on purpose:
--   * one OA source -> several Scopus ids when Scopus split a title history
--     that OpenAlex keeps as one record (legitimate, tier 1 on both);
--   * several OA duplicates -> one Scopus id.
-- Consumers wanting one-to-one filter on is_best_for_oa AND is_best_for_scopus.
CREATE TABLE IF NOT EXISTS matching.oa_scopus_source_map (
    oa_source_id       text NOT NULL,
    scopus_source_id   text NOT NULL REFERENCES scopus.sources ON DELETE CASCADE,
    match_method       text NOT NULL,   -- issn_l | issn_any | title_exact | title_fuzzy | manual
    tier               smallint NOT NULL, -- 1 accept | 2 review | 3 reject (manual only)
    score              real NOT NULL,
    is_best_for_oa     boolean NOT NULL DEFAULT false,
    is_best_for_scopus boolean NOT NULL DEFAULT false,
    evidence           jsonb NOT NULL DEFAULT '{}'::jsonb,
    decided_by         text NOT NULL DEFAULT 'auto',
    decided_at         timestamptz NOT NULL DEFAULT now(),
    run_id             text,
    PRIMARY KEY (oa_source_id, scopus_source_id)
);
CREATE INDEX IF NOT EXISTS oa_scopus_source_map_scopus_idx
    ON matching.oa_scopus_source_map (scopus_source_id) WHERE tier = 1;
CREATE INDEX IF NOT EXISTS oa_scopus_source_map_tier_idx
    ON matching.oa_scopus_source_map (tier);

-- FK to openalex.sources for introspection tools; NOT VALID like the rest of
-- the repo. Skipped (with a NOTICE) if sources has no primary key yet.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'oa_scopus_source_map_oa_source_id_fkey') THEN
        ALTER TABLE matching.oa_scopus_source_map
            ADD CONSTRAINT oa_scopus_source_map_oa_source_id_fkey
            FOREIGN KEY (oa_source_id) REFERENCES openalex.sources (id) NOT VALID;
    END IF;
EXCEPTION WHEN others THEN
    RAISE NOTICE 'skipping FK to openalex.sources: %', SQLERRM;
END $$;

-- Accepted crosswalk with ASJC codes attached: the join target for sampling.
CREATE OR REPLACE VIEW matching.oa_journal_asjc AS
SELECT m.oa_source_id, m.scopus_source_id, a.asjc_code, a.asjc_code / 100 AS area_code,
       s.coverage_start, s.coverage_end, m.match_method, m.score
FROM matching.oa_scopus_source_map m
JOIN scopus.sources s USING (scopus_source_id)
JOIN scopus.source_asjc a USING (scopus_source_id)
WHERE m.tier = 1;
