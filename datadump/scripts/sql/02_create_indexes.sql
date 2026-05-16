ALTER TABLE openalex.domains ADD PRIMARY KEY (id);

ALTER TABLE openalex.fields ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS fields_domain_id_idx ON openalex.fields (domain_id);

ALTER TABLE openalex.subfields ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS subfields_field_id_idx ON openalex.subfields (field_id);

ALTER TABLE openalex.topics ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS topics_subfield_id_idx ON openalex.topics (subfield_id);
CREATE INDEX IF NOT EXISTS topics_field_id_idx ON openalex.topics (field_id);
CREATE INDEX IF NOT EXISTS topics_domain_id_idx ON openalex.topics (domain_id);

ALTER TABLE openalex.keywords ADD PRIMARY KEY (id);

ALTER TABLE openalex.concepts ADD PRIMARY KEY (id);
ALTER TABLE openalex.concepts_ids ADD PRIMARY KEY (concept_id);

ALTER TABLE openalex.institutions ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS institutions_ror_idx ON openalex.institutions (ror);
CREATE INDEX IF NOT EXISTS institutions_country_code_idx ON openalex.institutions (country_code);
ALTER TABLE openalex.institutions_ids ADD PRIMARY KEY (institution_id);
ALTER TABLE openalex.institutions_geo ADD PRIMARY KEY (institution_id);
CREATE INDEX IF NOT EXISTS institutions_associated_institutions_institution_id_idx ON openalex.institutions_associated_institutions (institution_id);
ALTER TABLE openalex.institutions_counts_by_year ADD PRIMARY KEY (institution_id, year);
CREATE INDEX IF NOT EXISTS institutions_roles_institution_id_idx ON openalex.institutions_roles (institution_id);
CREATE INDEX IF NOT EXISTS institutions_repositories_institution_id_idx ON openalex.institutions_repositories (institution_id);

ALTER TABLE openalex.sources ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS sources_issn_l_idx ON openalex.sources (issn_l);
CREATE INDEX IF NOT EXISTS sources_host_organization_idx ON openalex.sources (host_organization);
CREATE INDEX IF NOT EXISTS sources_type_idx ON openalex.sources (type);
ALTER TABLE openalex.sources_ids ADD PRIMARY KEY (source_id);
ALTER TABLE openalex.sources_counts_by_year ADD PRIMARY KEY (source_id, year);

ALTER TABLE openalex.publishers ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS publishers_parent_publisher_idx ON openalex.publishers (parent_publisher);
ALTER TABLE openalex.publishers_ids ADD PRIMARY KEY (publisher_id);
ALTER TABLE openalex.publishers_counts_by_year ADD PRIMARY KEY (publisher_id, year);
CREATE INDEX IF NOT EXISTS publishers_roles_publisher_id_idx ON openalex.publishers_roles (publisher_id);

ALTER TABLE openalex.funders ADD PRIMARY KEY (id);
ALTER TABLE openalex.funders_ids ADD PRIMARY KEY (funder_id);
ALTER TABLE openalex.funders_counts_by_year ADD PRIMARY KEY (funder_id, year);
CREATE INDEX IF NOT EXISTS funders_roles_funder_id_idx ON openalex.funders_roles (funder_id);

ALTER TABLE openalex.authors ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS authors_orcid_idx ON openalex.authors (orcid);
ALTER TABLE openalex.authors_ids ADD PRIMARY KEY (author_id);
ALTER TABLE openalex.authors_counts_by_year ADD PRIMARY KEY (author_id, year);
CREATE INDEX IF NOT EXISTS authors_last_known_institutions_author_id_idx ON openalex.authors_last_known_institutions (author_id);
CREATE INDEX IF NOT EXISTS authors_last_known_institutions_institution_id_idx ON openalex.authors_last_known_institutions (institution_id);
CREATE INDEX IF NOT EXISTS authors_affiliations_author_id_idx ON openalex.authors_affiliations (author_id);
CREATE INDEX IF NOT EXISTS authors_affiliations_institution_id_idx ON openalex.authors_affiliations (institution_id);
CREATE INDEX IF NOT EXISTS authors_topics_author_id_idx ON openalex.authors_topics (author_id);
CREATE INDEX IF NOT EXISTS authors_topics_topic_id_idx ON openalex.authors_topics (topic_id);

ALTER TABLE openalex.awards ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS awards_funder_id_idx ON openalex.awards (funder_id);
CREATE INDEX IF NOT EXISTS awards_investigators_award_id_idx ON openalex.awards_investigators (award_id);

ALTER TABLE openalex.works ADD PRIMARY KEY (id);
CREATE INDEX IF NOT EXISTS works_doi_idx ON openalex.works (doi);
CREATE INDEX IF NOT EXISTS works_publication_year_idx ON openalex.works (publication_year);
CREATE INDEX IF NOT EXISTS works_type_idx ON openalex.works (type);
CREATE INDEX IF NOT EXISTS works_primary_topic_id_idx ON openalex.works (primary_topic_id);
CREATE INDEX IF NOT EXISTS works_primary_location_source_id_idx ON openalex.works (primary_location_source_id);
ALTER TABLE openalex.works_ids ADD PRIMARY KEY (work_id);
CREATE INDEX IF NOT EXISTS works_ids_pmid_idx ON openalex.works_ids (pmid);
CREATE INDEX IF NOT EXISTS works_locations_work_id_idx ON openalex.works_locations (work_id);
CREATE INDEX IF NOT EXISTS works_locations_source_id_idx ON openalex.works_locations (source_id);
ALTER TABLE openalex.works_open_access ADD PRIMARY KEY (work_id);
CREATE INDEX IF NOT EXISTS works_authorships_work_id_idx ON openalex.works_authorships (work_id);
CREATE INDEX IF NOT EXISTS works_authorships_author_id_idx ON openalex.works_authorships (author_id);
CREATE INDEX IF NOT EXISTS works_authorship_institutions_work_id_idx ON openalex.works_authorship_institutions (work_id);
CREATE INDEX IF NOT EXISTS works_authorship_institutions_author_id_idx ON openalex.works_authorship_institutions (author_id);
CREATE INDEX IF NOT EXISTS works_authorship_institutions_institution_id_idx ON openalex.works_authorship_institutions (institution_id);
CREATE INDEX IF NOT EXISTS works_authorship_countries_work_id_idx ON openalex.works_authorship_countries (work_id);
CREATE INDEX IF NOT EXISTS works_authorship_countries_author_id_idx ON openalex.works_authorship_countries (author_id);
ALTER TABLE openalex.works_biblio ADD PRIMARY KEY (work_id);
CREATE INDEX IF NOT EXISTS works_topics_work_id_idx ON openalex.works_topics (work_id);
CREATE INDEX IF NOT EXISTS works_topics_topic_id_idx ON openalex.works_topics (topic_id);
CREATE INDEX IF NOT EXISTS works_keywords_work_id_idx ON openalex.works_keywords (work_id);
CREATE INDEX IF NOT EXISTS works_keywords_keyword_id_idx ON openalex.works_keywords (keyword_id);
CREATE INDEX IF NOT EXISTS works_concepts_work_id_idx ON openalex.works_concepts (work_id);
CREATE INDEX IF NOT EXISTS works_concepts_concept_id_idx ON openalex.works_concepts (concept_id);
CREATE INDEX IF NOT EXISTS works_sdgs_work_id_idx ON openalex.works_sdgs (work_id);
CREATE INDEX IF NOT EXISTS works_mesh_work_id_idx ON openalex.works_mesh (work_id);
CREATE INDEX IF NOT EXISTS works_awards_work_id_idx ON openalex.works_awards (work_id);
CREATE INDEX IF NOT EXISTS works_awards_award_id_idx ON openalex.works_awards (award_id);
CREATE INDEX IF NOT EXISTS works_referenced_works_work_id_idx ON openalex.works_referenced_works (work_id);
CREATE INDEX IF NOT EXISTS works_referenced_works_referenced_work_id_idx ON openalex.works_referenced_works (referenced_work_id);
CREATE INDEX IF NOT EXISTS works_related_works_work_id_idx ON openalex.works_related_works (work_id);
CREATE INDEX IF NOT EXISTS works_counts_by_year_work_id_idx ON openalex.works_counts_by_year (work_id);

