-- Phase 2c (optional) — declare foreign-key relationships so that introspection
-- tools (the VS Code pg extension, DBeaver, pgAdmin, dbdiagram.io exports,
-- planner row-count estimates, …) can see them.
--
-- Run AFTER 02_create_indexes.sql (FKs require a unique index on the parent
-- column). All constraints are declared NOT VALID for two reasons:
--   1. NOT VALID skips the full-table existence check on creation — instant
--      vs. hours on the works-side tables.
--   2. OpenAlex snapshots routinely contain orphan references (a Work cites
--      a Work that hasn't been ingested yet, an authorship points at a soft-
--      deleted Author, etc.). A VALIDATE pass would fail on real data.
--
-- NOT VALID constraints are still enforced for *new* rows and are shown by
-- introspection tools, so the relationship-viewer use case works fine. If
-- later you want to enforce them on the existing rows you can run
--   ALTER TABLE ... VALIDATE CONSTRAINT <name>;
-- per constraint, but expect failures on the works-side ones.

-- ── topic hierarchy ──────────────────────────────────────────────────────
ALTER TABLE openalex.fields
  ADD CONSTRAINT fields_domain_id_fkey
  FOREIGN KEY (domain_id) REFERENCES openalex.domains(id) NOT VALID;

ALTER TABLE openalex.subfields
  ADD CONSTRAINT subfields_field_id_fkey
  FOREIGN KEY (field_id) REFERENCES openalex.fields(id) NOT VALID;

ALTER TABLE openalex.topics
  ADD CONSTRAINT topics_subfield_id_fkey
  FOREIGN KEY (subfield_id) REFERENCES openalex.subfields(id) NOT VALID;

ALTER TABLE openalex.topics
  ADD CONSTRAINT topics_field_id_fkey
  FOREIGN KEY (field_id) REFERENCES openalex.fields(id) NOT VALID;

ALTER TABLE openalex.topics
  ADD CONSTRAINT topics_domain_id_fkey
  FOREIGN KEY (domain_id) REFERENCES openalex.domains(id) NOT VALID;

-- ── authors ──────────────────────────────────────────────────────────────
ALTER TABLE openalex.authors_ids
  ADD CONSTRAINT authors_ids_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.authors_counts_by_year
  ADD CONSTRAINT authors_counts_by_year_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.authors_last_known_institutions
  ADD CONSTRAINT authors_last_known_institutions_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.authors_last_known_institutions
  ADD CONSTRAINT authors_last_known_institutions_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.authors_affiliations
  ADD CONSTRAINT authors_affiliations_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.authors_affiliations
  ADD CONSTRAINT authors_affiliations_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.authors_topics
  ADD CONSTRAINT authors_topics_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.authors_topics
  ADD CONSTRAINT authors_topics_topic_id_fkey
  FOREIGN KEY (topic_id) REFERENCES openalex.topics(id) NOT VALID;

-- ── institutions ─────────────────────────────────────────────────────────
ALTER TABLE openalex.institutions_ids
  ADD CONSTRAINT institutions_ids_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.institutions_geo
  ADD CONSTRAINT institutions_geo_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.institutions_counts_by_year
  ADD CONSTRAINT institutions_counts_by_year_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.institutions_associated_institutions
  ADD CONSTRAINT institutions_associated_institutions_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.institutions_roles
  ADD CONSTRAINT institutions_roles_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.institutions_repositories
  ADD CONSTRAINT institutions_repositories_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

-- ── sources ──────────────────────────────────────────────────────────────
ALTER TABLE openalex.sources_ids
  ADD CONSTRAINT sources_ids_source_id_fkey
  FOREIGN KEY (source_id) REFERENCES openalex.sources(id) NOT VALID;

ALTER TABLE openalex.sources_counts_by_year
  ADD CONSTRAINT sources_counts_by_year_source_id_fkey
  FOREIGN KEY (source_id) REFERENCES openalex.sources(id) NOT VALID;

-- ── publishers ───────────────────────────────────────────────────────────
ALTER TABLE openalex.publishers_ids
  ADD CONSTRAINT publishers_ids_publisher_id_fkey
  FOREIGN KEY (publisher_id) REFERENCES openalex.publishers(id) NOT VALID;

ALTER TABLE openalex.publishers_counts_by_year
  ADD CONSTRAINT publishers_counts_by_year_publisher_id_fkey
  FOREIGN KEY (publisher_id) REFERENCES openalex.publishers(id) NOT VALID;

ALTER TABLE openalex.publishers_roles
  ADD CONSTRAINT publishers_roles_publisher_id_fkey
  FOREIGN KEY (publisher_id) REFERENCES openalex.publishers(id) NOT VALID;

-- ── funders ──────────────────────────────────────────────────────────────
ALTER TABLE openalex.funders_ids
  ADD CONSTRAINT funders_ids_funder_id_fkey
  FOREIGN KEY (funder_id) REFERENCES openalex.funders(id) NOT VALID;

ALTER TABLE openalex.funders_counts_by_year
  ADD CONSTRAINT funders_counts_by_year_funder_id_fkey
  FOREIGN KEY (funder_id) REFERENCES openalex.funders(id) NOT VALID;

ALTER TABLE openalex.funders_roles
  ADD CONSTRAINT funders_roles_funder_id_fkey
  FOREIGN KEY (funder_id) REFERENCES openalex.funders(id) NOT VALID;

-- ── concepts (deprecated, still shipped) ─────────────────────────────────
ALTER TABLE openalex.concepts_ids
  ADD CONSTRAINT concepts_ids_concept_id_fkey
  FOREIGN KEY (concept_id) REFERENCES openalex.concepts(id) NOT VALID;

-- ── awards ───────────────────────────────────────────────────────────────
ALTER TABLE openalex.awards
  ADD CONSTRAINT awards_funder_id_fkey
  FOREIGN KEY (funder_id) REFERENCES openalex.funders(id) NOT VALID;

ALTER TABLE openalex.awards_investigators
  ADD CONSTRAINT awards_investigators_award_id_fkey
  FOREIGN KEY (award_id) REFERENCES openalex.awards(id) NOT VALID;

-- ── works (the big ones) ─────────────────────────────────────────────────
-- Many of these will have orphans in any snapshot — only the constraint
-- declaration is what the introspection tools need; data integrity is
-- expected to be best-effort.
ALTER TABLE openalex.works
  ADD CONSTRAINT works_primary_topic_id_fkey
  FOREIGN KEY (primary_topic_id) REFERENCES openalex.topics(id) NOT VALID;

ALTER TABLE openalex.works
  ADD CONSTRAINT works_primary_location_source_id_fkey
  FOREIGN KEY (primary_location_source_id) REFERENCES openalex.sources(id) NOT VALID;

ALTER TABLE openalex.works_ids
  ADD CONSTRAINT works_ids_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_biblio
  ADD CONSTRAINT works_biblio_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_open_access
  ADD CONSTRAINT works_open_access_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_counts_by_year
  ADD CONSTRAINT works_counts_by_year_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_locations
  ADD CONSTRAINT works_locations_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_locations
  ADD CONSTRAINT works_locations_source_id_fkey
  FOREIGN KEY (source_id) REFERENCES openalex.sources(id) NOT VALID;

ALTER TABLE openalex.works_authorships
  ADD CONSTRAINT works_authorships_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_authorships
  ADD CONSTRAINT works_authorships_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.works_authorship_institutions
  ADD CONSTRAINT works_authorship_institutions_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_authorship_institutions
  ADD CONSTRAINT works_authorship_institutions_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.works_authorship_institutions
  ADD CONSTRAINT works_authorship_institutions_institution_id_fkey
  FOREIGN KEY (institution_id) REFERENCES openalex.institutions(id) NOT VALID;

ALTER TABLE openalex.works_authorship_countries
  ADD CONSTRAINT works_authorship_countries_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_authorship_countries
  ADD CONSTRAINT works_authorship_countries_author_id_fkey
  FOREIGN KEY (author_id) REFERENCES openalex.authors(id) NOT VALID;

ALTER TABLE openalex.works_topics
  ADD CONSTRAINT works_topics_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_topics
  ADD CONSTRAINT works_topics_topic_id_fkey
  FOREIGN KEY (topic_id) REFERENCES openalex.topics(id) NOT VALID;

ALTER TABLE openalex.works_keywords
  ADD CONSTRAINT works_keywords_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_keywords
  ADD CONSTRAINT works_keywords_keyword_id_fkey
  FOREIGN KEY (keyword_id) REFERENCES openalex.keywords(id) NOT VALID;

ALTER TABLE openalex.works_concepts
  ADD CONSTRAINT works_concepts_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_concepts
  ADD CONSTRAINT works_concepts_concept_id_fkey
  FOREIGN KEY (concept_id) REFERENCES openalex.concepts(id) NOT VALID;

ALTER TABLE openalex.works_sdgs
  ADD CONSTRAINT works_sdgs_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_mesh
  ADD CONSTRAINT works_mesh_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_awards
  ADD CONSTRAINT works_awards_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_awards
  ADD CONSTRAINT works_awards_award_id_fkey
  FOREIGN KEY (award_id) REFERENCES openalex.awards(id) NOT VALID;

ALTER TABLE openalex.works_referenced_works
  ADD CONSTRAINT works_referenced_works_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_referenced_works
  ADD CONSTRAINT works_referenced_works_referenced_work_id_fkey
  FOREIGN KEY (referenced_work_id) REFERENCES openalex.works(id) NOT VALID;

ALTER TABLE openalex.works_related_works
  ADD CONSTRAINT works_related_works_work_id_fkey
  FOREIGN KEY (work_id) REFERENCES openalex.works(id) NOT VALID;
