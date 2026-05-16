CREATE SCHEMA IF NOT EXISTS openalex;

DROP TABLE IF EXISTS openalex.domains CASCADE;
CREATE TABLE openalex.domains (
    id text,
    display_name text,
    description text,
    works_count bigint,
    cited_by_count bigint,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.fields CASCADE;
CREATE TABLE openalex.fields (
    id text,
    display_name text,
    description text,
    domain_id text,
    works_count bigint,
    cited_by_count bigint,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.subfields CASCADE;
CREATE TABLE openalex.subfields (
    id text,
    display_name text,
    description text,
    field_id text,
    domain_id text,
    works_count bigint,
    cited_by_count bigint,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.topics CASCADE;
CREATE TABLE openalex.topics (
    id text,
    display_name text,
    description text,
    keywords jsonb,
    subfield_id text,
    subfield_display_name text,
    field_id text,
    field_display_name text,
    domain_id text,
    domain_display_name text,
    wikipedia_id text,
    works_count bigint,
    cited_by_count bigint,
    works_api_url text,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.keywords CASCADE;
CREATE TABLE openalex.keywords (
    id text,
    display_name text,
    works_count bigint,
    cited_by_count bigint,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.concepts CASCADE;
CREATE TABLE openalex.concepts (
    id text,
    wikidata text,
    display_name text,
    level integer,
    description text,
    works_count bigint,
    cited_by_count bigint,
    image_url text,
    image_thumbnail_url text,
    works_api_url text,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.concepts_ids CASCADE;
CREATE TABLE openalex.concepts_ids (
    concept_id text,
    openalex text,
    wikidata text,
    wikipedia text,
    umls_aui jsonb,
    umls_cui jsonb,
    mag bigint
);

DROP TABLE IF EXISTS openalex.concepts_ancestors CASCADE;
CREATE TABLE openalex.concepts_ancestors (
    concept_id text,
    ancestor_id text
);

DROP TABLE IF EXISTS openalex.concepts_related_concepts CASCADE;
CREATE TABLE openalex.concepts_related_concepts (
    concept_id text,
    related_concept_id text,
    score real
);

DROP TABLE IF EXISTS openalex.concepts_counts_by_year CASCADE;
CREATE TABLE openalex.concepts_counts_by_year (
    concept_id text,
    year integer,
    works_count bigint,
    cited_by_count bigint
);

DROP TABLE IF EXISTS openalex.institutions CASCADE;
CREATE TABLE openalex.institutions (
    id text,
    ror text,
    display_name text,
    country_code text,
    type text,
    type_id text,
    lineage jsonb,
    is_super_system boolean,
    homepage_url text,
    image_url text,
    image_thumbnail_url text,
    display_name_acronyms jsonb,
    display_name_alternatives jsonb,
    works_count bigint,
    cited_by_count bigint,
    mean_citedness_2yr real,
    h_index integer,
    i10_index integer,
    status text,
    works_api_url text,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.institutions_ids CASCADE;
CREATE TABLE openalex.institutions_ids (
    institution_id text,
    openalex text,
    ror text,
    grid text,
    wikipedia text,
    wikidata text,
    mag bigint
);

DROP TABLE IF EXISTS openalex.institutions_geo CASCADE;
CREATE TABLE openalex.institutions_geo (
    institution_id text,
    city text,
    geonames_city_id text,
    region text,
    country_code text,
    country text,
    latitude real,
    longitude real
);

DROP TABLE IF EXISTS openalex.institutions_associated_institutions CASCADE;
CREATE TABLE openalex.institutions_associated_institutions (
    institution_id text,
    associated_institution_id text,
    relationship text
);

DROP TABLE IF EXISTS openalex.institutions_counts_by_year CASCADE;
CREATE TABLE openalex.institutions_counts_by_year (
    institution_id text,
    year integer,
    works_count bigint,
    cited_by_count bigint
);

DROP TABLE IF EXISTS openalex.institutions_roles CASCADE;
CREATE TABLE openalex.institutions_roles (
    institution_id text,
    role text,
    role_id text,
    works_count bigint
);

DROP TABLE IF EXISTS openalex.institutions_repositories CASCADE;
CREATE TABLE openalex.institutions_repositories (
    institution_id text,
    repository_id text,
    display_name text
);

DROP TABLE IF EXISTS openalex.sources CASCADE;
CREATE TABLE openalex.sources (
    id text,
    issn_l text,
    issn jsonb,
    display_name text,
    host_organization text,
    host_organization_name text,
    host_organization_lineage jsonb,
    works_count bigint,
    oa_works_count bigint,
    cited_by_count bigint,
    mean_citedness_2yr real,
    h_index integer,
    i10_index integer,
    is_oa boolean,
    is_in_doaj boolean,
    is_in_scielo boolean,
    is_core boolean,
    is_ojs boolean,
    is_high_oa_rate boolean,
    oa_flip_year integer,
    type text,
    apc_usd integer,
    country_code text,
    homepage_url text,
    first_publication_year integer,
    last_publication_year integer,
    alternate_titles jsonb,
    societies jsonb,
    apc_prices jsonb,
    works_api_url text,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.sources_ids CASCADE;
CREATE TABLE openalex.sources_ids (
    source_id text,
    openalex text,
    issn_l text,
    issn jsonb,
    mag bigint,
    wikidata text,
    fatcat text
);

DROP TABLE IF EXISTS openalex.sources_counts_by_year CASCADE;
CREATE TABLE openalex.sources_counts_by_year (
    source_id text,
    year integer,
    works_count bigint,
    oa_works_count bigint,
    cited_by_count bigint
);

DROP TABLE IF EXISTS openalex.publishers CASCADE;
CREATE TABLE openalex.publishers (
    id text,
    display_name text,
    alternate_titles jsonb,
    country_codes jsonb,
    hierarchy_level integer,
    parent_publisher text,
    lineage jsonb,
    homepage_url text,
    image_url text,
    image_thumbnail_url text,
    ror_id text,
    wikidata_id text,
    works_count bigint,
    cited_by_count bigint,
    mean_citedness_2yr real,
    h_index integer,
    i10_index integer,
    sources_api_url text,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.publishers_ids CASCADE;
CREATE TABLE openalex.publishers_ids (
    publisher_id text,
    openalex text,
    ror text,
    wikidata text
);

DROP TABLE IF EXISTS openalex.publishers_counts_by_year CASCADE;
CREATE TABLE openalex.publishers_counts_by_year (
    publisher_id text,
    year integer,
    works_count bigint,
    cited_by_count bigint
);

DROP TABLE IF EXISTS openalex.publishers_roles CASCADE;
CREATE TABLE openalex.publishers_roles (
    publisher_id text,
    role text,
    role_id text,
    works_count bigint
);

DROP TABLE IF EXISTS openalex.funders CASCADE;
CREATE TABLE openalex.funders (
    id text,
    display_name text,
    alternate_titles jsonb,
    country_code text,
    description text,
    homepage_url text,
    image_url text,
    image_thumbnail_url text,
    works_count bigint,
    cited_by_count bigint,
    awards_count bigint,
    mean_citedness_2yr real,
    h_index integer,
    i10_index integer,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.funders_ids CASCADE;
CREATE TABLE openalex.funders_ids (
    funder_id text,
    openalex text,
    ror text,
    wikidata text,
    crossref text,
    doi text
);

DROP TABLE IF EXISTS openalex.funders_counts_by_year CASCADE;
CREATE TABLE openalex.funders_counts_by_year (
    funder_id text,
    year integer,
    works_count bigint,
    oa_works_count bigint,
    cited_by_count bigint
);

DROP TABLE IF EXISTS openalex.funders_roles CASCADE;
CREATE TABLE openalex.funders_roles (
    funder_id text,
    role text,
    role_id text,
    works_count bigint
);

DROP TABLE IF EXISTS openalex.authors CASCADE;
CREATE TABLE openalex.authors (
    id text,
    orcid text,
    display_name text,
    display_name_alternatives jsonb,
    works_count bigint,
    cited_by_count bigint,
    mean_citedness_2yr real,
    h_index integer,
    i10_index integer,
    works_api_url text,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.authors_ids CASCADE;
CREATE TABLE openalex.authors_ids (
    author_id text,
    openalex text,
    orcid text,
    scopus text,
    twitter text,
    wikipedia text,
    mag bigint
);

DROP TABLE IF EXISTS openalex.authors_counts_by_year CASCADE;
CREATE TABLE openalex.authors_counts_by_year (
    author_id text,
    year integer,
    works_count bigint,
    oa_works_count bigint,
    cited_by_count bigint
);

DROP TABLE IF EXISTS openalex.authors_last_known_institutions CASCADE;
CREATE TABLE openalex.authors_last_known_institutions (
    author_id text,
    institution_id text
);

DROP TABLE IF EXISTS openalex.authors_affiliations CASCADE;
CREATE TABLE openalex.authors_affiliations (
    author_id text,
    institution_id text,
    years jsonb
);

DROP TABLE IF EXISTS openalex.authors_topics CASCADE;
CREATE TABLE openalex.authors_topics (
    author_id text,
    topic_id text,
    count integer,
    score real
);

DROP TABLE IF EXISTS openalex.awards CASCADE;
CREATE TABLE openalex.awards (
    id text,
    display_name text,
    description text,
    funder_award_id text,
    amount double precision,
    currency text,
    funder_id text,
    funder_display_name text,
    funder_ror_id text,
    funder_doi text,
    funding_type text,
    funder_scheme text,
    provenance text,
    start_date date,
    end_date date,
    start_year integer,
    end_year integer,
    landing_page_url text,
    doi text,
    works_api_url text,
    funded_outputs_count bigint,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.awards_investigators CASCADE;
CREATE TABLE openalex.awards_investigators (
    award_id text,
    role text,
    given_name text,
    family_name text,
    orcid text,
    affiliation_name text,
    affiliation_country text
);

DROP TABLE IF EXISTS openalex.works CASCADE;
CREATE TABLE openalex.works (
    id text,
    doi text,
    title text,
    display_name text,
    publication_year integer,
    publication_date date,
    language text,
    type text,
    countries_distinct_count integer,
    institutions_distinct_count integer,
    authors_count integer,
    locations_count integer,
    referenced_works_count integer,
    fwci double precision,
    has_fulltext boolean,
    has_content jsonb,
    is_retracted boolean,
    is_paratext boolean,
    is_xpac boolean,
    cited_by_count bigint,
    cited_by_percentile_year_min integer,
    cited_by_percentile_year_max integer,
    citation_normalized_percentile double precision,
    is_in_top_1_percent boolean,
    is_in_top_10_percent boolean,
    primary_topic_id text,
    primary_location_source_id text,
    indexed_in jsonb,
    apc_list jsonb,
    apc_paid jsonb,
    abstract_inverted_index jsonb,
    updated_date timestamptz,
    created_date timestamptz
);

DROP TABLE IF EXISTS openalex.works_ids CASCADE;
CREATE TABLE openalex.works_ids (
    work_id text,
    openalex text,
    doi text,
    mag bigint,
    pmid text,
    pmcid text
);

DROP TABLE IF EXISTS openalex.works_locations CASCADE;
CREATE TABLE openalex.works_locations (
    work_id text,
    location_position integer,
    is_primary boolean,
    is_best_oa boolean,
    source_id text,
    landing_page_url text,
    pdf_url text,
    is_oa boolean,
    version text,
    license text,
    license_id text,
    is_published boolean,
    is_accepted boolean,
    raw_source_name text,
    provenance text
);

DROP TABLE IF EXISTS openalex.works_open_access CASCADE;
CREATE TABLE openalex.works_open_access (
    work_id text,
    is_oa boolean,
    oa_status text,
    oa_url text,
    any_repository_has_fulltext boolean
);

DROP TABLE IF EXISTS openalex.works_authorships CASCADE;
CREATE TABLE openalex.works_authorships (
    work_id text,
    author_position text,
    author_id text,
    author_display_name text,
    raw_author_name text,
    is_corresponding boolean
);

DROP TABLE IF EXISTS openalex.works_authorship_institutions CASCADE;
CREATE TABLE openalex.works_authorship_institutions (
    work_id text,
    author_id text,
    institution_id text
);

DROP TABLE IF EXISTS openalex.works_authorship_countries CASCADE;
CREATE TABLE openalex.works_authorship_countries (
    work_id text,
    author_id text,
    country_code text
);

DROP TABLE IF EXISTS openalex.works_biblio CASCADE;
CREATE TABLE openalex.works_biblio (
    work_id text,
    volume text,
    issue text,
    first_page text,
    last_page text
);

DROP TABLE IF EXISTS openalex.works_topics CASCADE;
CREATE TABLE openalex.works_topics (
    work_id text,
    topic_id text,
    score real,
    is_primary boolean
);

DROP TABLE IF EXISTS openalex.works_keywords CASCADE;
CREATE TABLE openalex.works_keywords (
    work_id text,
    keyword_id text,
    score real
);

DROP TABLE IF EXISTS openalex.works_concepts CASCADE;
CREATE TABLE openalex.works_concepts (
    work_id text,
    concept_id text,
    score real
);

DROP TABLE IF EXISTS openalex.works_sdgs CASCADE;
CREATE TABLE openalex.works_sdgs (
    work_id text,
    sdg_id text,
    display_name text,
    score real
);

DROP TABLE IF EXISTS openalex.works_mesh CASCADE;
CREATE TABLE openalex.works_mesh (
    work_id text,
    descriptor_ui text,
    descriptor_name text,
    qualifier_ui text,
    qualifier_name text,
    is_major_topic boolean
);

DROP TABLE IF EXISTS openalex.works_grants CASCADE;
CREATE TABLE openalex.works_grants (
    work_id text,
    funder_id text,
    funder_display_name text,
    award_id text
);

DROP TABLE IF EXISTS openalex.works_awards CASCADE;
CREATE TABLE openalex.works_awards (
    work_id text,
    award_id text
);

DROP TABLE IF EXISTS openalex.works_referenced_works CASCADE;
CREATE TABLE openalex.works_referenced_works (
    work_id text,
    referenced_work_id text
);

DROP TABLE IF EXISTS openalex.works_related_works CASCADE;
CREATE TABLE openalex.works_related_works (
    work_id text,
    related_work_id text
);

DROP TABLE IF EXISTS openalex.works_counts_by_year CASCADE;
CREATE TABLE openalex.works_counts_by_year (
    work_id text,
    year integer,
    cited_by_count bigint
);

