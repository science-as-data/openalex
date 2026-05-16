"""Single source of truth for the OpenAlex -> PostgreSQL load.

Defines, for every entity in the snapshot:
  * TABLES   - the relational tables and their (column, sql_type) lists
  * EXTRACTORS - a function turning one JSON record into {table: [row_dict, ...]}

`flatten.py` imports EXTRACTORS to write CSVs; `gen_sql.py` imports TABLES to
generate the CREATE TABLE / \\copy / index SQL.  Keeping all three in sync from
one place is the whole point of this file.

Built against the OpenAlex standard-format snapshot, RELEASE 2026-03-30.
The official richard-orr gist scripts are from 2022 and target the retired
`venues`/`host_venue` model -- this file replaces them.
"""

import json

# Entities loaded, in dependency-friendly order (lookups first, works last).
ENTITIES = [
    "domains", "fields", "subfields", "topics", "keywords", "concepts",
    "institutions", "sources", "publishers", "funders", "authors",
    "awards", "works",
]

# ID prefix kept as-is (full URL) so every *_id column joins directly.
# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------


def j(v):
    """JSON-encode a dict/list for a json column; leave None as None."""
    if v is None:
        return None
    return json.dumps(v, ensure_ascii=False)


def stats(obj):
    s = obj.get("summary_stats") or {}
    return (s.get("2yr_mean_citedness"), s.get("h_index"), s.get("i10_index"))


# ----------------------------------------------------------------------------
# table definitions: entity -> { table_name: [(column, sql_type), ...] }
# ----------------------------------------------------------------------------

TABLES = {
    "domains": {
        "domains": [
            ("id", "text"), ("display_name", "text"), ("description", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
    },
    "fields": {
        "fields": [
            ("id", "text"), ("display_name", "text"), ("description", "text"),
            ("domain_id", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
    },
    "subfields": {
        "subfields": [
            ("id", "text"), ("display_name", "text"), ("description", "text"),
            ("field_id", "text"), ("domain_id", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
    },
    "topics": {
        "topics": [
            ("id", "text"), ("display_name", "text"), ("description", "text"),
            ("keywords", "jsonb"),
            ("subfield_id", "text"), ("subfield_display_name", "text"),
            ("field_id", "text"), ("field_display_name", "text"),
            ("domain_id", "text"), ("domain_display_name", "text"),
            ("wikipedia_id", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("works_api_url", "text"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
    },
    "keywords": {
        "keywords": [
            ("id", "text"), ("display_name", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
    },
    "concepts": {
        "concepts": [
            ("id", "text"), ("wikidata", "text"), ("display_name", "text"),
            ("level", "integer"), ("description", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("image_url", "text"), ("image_thumbnail_url", "text"),
            ("works_api_url", "text"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "concepts_ids": [
            ("concept_id", "text"), ("openalex", "text"), ("wikidata", "text"),
            ("wikipedia", "text"), ("umls_aui", "jsonb"), ("umls_cui", "jsonb"),
            ("mag", "bigint"),
        ],
        "concepts_ancestors": [
            ("concept_id", "text"), ("ancestor_id", "text"),
        ],
        "concepts_related_concepts": [
            ("concept_id", "text"), ("related_concept_id", "text"),
            ("score", "real"),
        ],
        "concepts_counts_by_year": [
            ("concept_id", "text"), ("year", "integer"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
        ],
    },
    "institutions": {
        "institutions": [
            ("id", "text"), ("ror", "text"), ("display_name", "text"),
            ("country_code", "text"), ("type", "text"), ("type_id", "text"),
            ("lineage", "jsonb"), ("is_super_system", "boolean"),
            ("homepage_url", "text"), ("image_url", "text"),
            ("image_thumbnail_url", "text"),
            ("display_name_acronyms", "jsonb"),
            ("display_name_alternatives", "jsonb"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("mean_citedness_2yr", "real"), ("h_index", "integer"),
            ("i10_index", "integer"), ("status", "text"),
            ("works_api_url", "text"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "institutions_ids": [
            ("institution_id", "text"), ("openalex", "text"), ("ror", "text"),
            ("grid", "text"), ("wikipedia", "text"), ("wikidata", "text"),
            ("mag", "bigint"),
        ],
        "institutions_geo": [
            ("institution_id", "text"), ("city", "text"),
            ("geonames_city_id", "text"), ("region", "text"),
            ("country_code", "text"), ("country", "text"),
            ("latitude", "real"), ("longitude", "real"),
        ],
        "institutions_associated_institutions": [
            ("institution_id", "text"),
            ("associated_institution_id", "text"), ("relationship", "text"),
        ],
        "institutions_counts_by_year": [
            ("institution_id", "text"), ("year", "integer"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
        ],
        "institutions_roles": [
            ("institution_id", "text"), ("role", "text"),
            ("role_id", "text"), ("works_count", "bigint"),
        ],
        "institutions_repositories": [
            ("institution_id", "text"), ("repository_id", "text"),
            ("display_name", "text"),
        ],
    },
    "sources": {
        "sources": [
            ("id", "text"), ("issn_l", "text"), ("issn", "jsonb"),
            ("display_name", "text"), ("host_organization", "text"),
            ("host_organization_name", "text"),
            ("host_organization_lineage", "jsonb"),
            ("works_count", "bigint"), ("oa_works_count", "bigint"),
            ("cited_by_count", "bigint"),
            ("mean_citedness_2yr", "real"), ("h_index", "integer"),
            ("i10_index", "integer"),
            ("is_oa", "boolean"), ("is_in_doaj", "boolean"),
            ("is_in_scielo", "boolean"), ("is_core", "boolean"),
            ("is_ojs", "boolean"), ("is_high_oa_rate", "boolean"),
            ("oa_flip_year", "integer"), ("type", "text"),
            ("apc_usd", "integer"), ("country_code", "text"),
            ("homepage_url", "text"),
            ("first_publication_year", "integer"),
            ("last_publication_year", "integer"),
            ("alternate_titles", "jsonb"), ("societies", "jsonb"),
            ("apc_prices", "jsonb"), ("works_api_url", "text"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "sources_ids": [
            ("source_id", "text"), ("openalex", "text"), ("issn_l", "text"),
            ("issn", "jsonb"), ("mag", "bigint"), ("wikidata", "text"),
            ("fatcat", "text"),
        ],
        "sources_counts_by_year": [
            ("source_id", "text"), ("year", "integer"),
            ("works_count", "bigint"), ("oa_works_count", "bigint"),
            ("cited_by_count", "bigint"),
        ],
    },
    "publishers": {
        "publishers": [
            ("id", "text"), ("display_name", "text"),
            ("alternate_titles", "jsonb"), ("country_codes", "jsonb"),
            ("hierarchy_level", "integer"), ("parent_publisher", "text"),
            ("lineage", "jsonb"), ("homepage_url", "text"),
            ("image_url", "text"), ("image_thumbnail_url", "text"),
            ("ror_id", "text"), ("wikidata_id", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("mean_citedness_2yr", "real"), ("h_index", "integer"),
            ("i10_index", "integer"), ("sources_api_url", "text"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "publishers_ids": [
            ("publisher_id", "text"), ("openalex", "text"), ("ror", "text"),
            ("wikidata", "text"),
        ],
        "publishers_counts_by_year": [
            ("publisher_id", "text"), ("year", "integer"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
        ],
        "publishers_roles": [
            ("publisher_id", "text"), ("role", "text"),
            ("role_id", "text"), ("works_count", "bigint"),
        ],
    },
    "funders": {
        "funders": [
            ("id", "text"), ("display_name", "text"),
            ("alternate_titles", "jsonb"), ("country_code", "text"),
            ("description", "text"), ("homepage_url", "text"),
            ("image_url", "text"), ("image_thumbnail_url", "text"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("awards_count", "bigint"),
            ("mean_citedness_2yr", "real"), ("h_index", "integer"),
            ("i10_index", "integer"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "funders_ids": [
            ("funder_id", "text"), ("openalex", "text"), ("ror", "text"),
            ("wikidata", "text"), ("crossref", "text"), ("doi", "text"),
        ],
        "funders_counts_by_year": [
            ("funder_id", "text"), ("year", "integer"),
            ("works_count", "bigint"), ("oa_works_count", "bigint"),
            ("cited_by_count", "bigint"),
        ],
        "funders_roles": [
            ("funder_id", "text"), ("role", "text"),
            ("role_id", "text"), ("works_count", "bigint"),
        ],
    },
    "authors": {
        "authors": [
            ("id", "text"), ("orcid", "text"), ("display_name", "text"),
            ("display_name_alternatives", "jsonb"),
            ("works_count", "bigint"), ("cited_by_count", "bigint"),
            ("mean_citedness_2yr", "real"), ("h_index", "integer"),
            ("i10_index", "integer"), ("works_api_url", "text"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "authors_ids": [
            ("author_id", "text"), ("openalex", "text"), ("orcid", "text"),
            ("scopus", "text"), ("twitter", "text"), ("wikipedia", "text"),
            ("mag", "bigint"),
        ],
        "authors_counts_by_year": [
            ("author_id", "text"), ("year", "integer"),
            ("works_count", "bigint"), ("oa_works_count", "bigint"),
            ("cited_by_count", "bigint"),
        ],
        "authors_last_known_institutions": [
            ("author_id", "text"), ("institution_id", "text"),
        ],
        "authors_affiliations": [
            ("author_id", "text"), ("institution_id", "text"),
            ("years", "jsonb"),
        ],
        "authors_topics": [
            ("author_id", "text"), ("topic_id", "text"),
            ("count", "integer"), ("score", "real"),
        ],
    },
    "awards": {
        "awards": [
            ("id", "text"), ("display_name", "text"), ("description", "text"),
            ("funder_award_id", "text"), ("amount", "double precision"),
            ("currency", "text"), ("funder_id", "text"),
            ("funder_display_name", "text"), ("funder_ror_id", "text"),
            ("funder_doi", "text"), ("funding_type", "text"),
            ("funder_scheme", "text"), ("provenance", "text"),
            ("start_date", "date"), ("end_date", "date"),
            ("start_year", "integer"), ("end_year", "integer"),
            ("landing_page_url", "text"), ("doi", "text"),
            ("works_api_url", "text"), ("funded_outputs_count", "bigint"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "awards_investigators": [
            ("award_id", "text"), ("role", "text"), ("given_name", "text"),
            ("family_name", "text"), ("orcid", "text"),
            ("affiliation_name", "text"), ("affiliation_country", "text"),
        ],
    },
    "works": {
        "works": [
            ("id", "text"), ("doi", "text"), ("title", "text"),
            ("display_name", "text"), ("publication_year", "integer"),
            ("publication_date", "date"), ("language", "text"),
            ("type", "text"),
            ("countries_distinct_count", "integer"),
            ("institutions_distinct_count", "integer"),
            ("authors_count", "integer"), ("locations_count", "integer"),
            ("referenced_works_count", "integer"),
            ("fwci", "double precision"),
            ("has_fulltext", "boolean"), ("has_content", "jsonb"),
            ("is_retracted", "boolean"), ("is_paratext", "boolean"),
            ("is_xpac", "boolean"),
            ("cited_by_count", "bigint"),
            ("cited_by_percentile_year_min", "integer"),
            ("cited_by_percentile_year_max", "integer"),
            ("citation_normalized_percentile", "double precision"),
            ("is_in_top_1_percent", "boolean"),
            ("is_in_top_10_percent", "boolean"),
            ("primary_topic_id", "text"),
            ("primary_location_source_id", "text"),
            ("indexed_in", "jsonb"), ("apc_list", "jsonb"),
            ("apc_paid", "jsonb"), ("abstract_inverted_index", "jsonb"),
            ("updated_date", "timestamptz"), ("created_date", "timestamptz"),
        ],
        "works_ids": [
            ("work_id", "text"), ("openalex", "text"), ("doi", "text"),
            ("mag", "bigint"), ("pmid", "text"), ("pmcid", "text"),
        ],
        "works_locations": [
            ("work_id", "text"), ("location_position", "integer"),
            ("is_primary", "boolean"), ("is_best_oa", "boolean"),
            ("source_id", "text"), ("landing_page_url", "text"),
            ("pdf_url", "text"), ("is_oa", "boolean"), ("version", "text"),
            ("license", "text"), ("license_id", "text"),
            ("is_published", "boolean"), ("is_accepted", "boolean"),
            ("raw_source_name", "text"), ("provenance", "text"),
        ],
        "works_open_access": [
            ("work_id", "text"), ("is_oa", "boolean"), ("oa_status", "text"),
            ("oa_url", "text"), ("any_repository_has_fulltext", "boolean"),
        ],
        "works_authorships": [
            ("work_id", "text"), ("author_position", "text"),
            ("author_id", "text"), ("author_display_name", "text"),
            ("raw_author_name", "text"), ("is_corresponding", "boolean"),
        ],
        "works_authorship_institutions": [
            ("work_id", "text"), ("author_id", "text"),
            ("institution_id", "text"),
        ],
        "works_authorship_countries": [
            ("work_id", "text"), ("author_id", "text"),
            ("country_code", "text"),
        ],
        "works_biblio": [
            ("work_id", "text"), ("volume", "text"), ("issue", "text"),
            ("first_page", "text"), ("last_page", "text"),
        ],
        "works_topics": [
            ("work_id", "text"), ("topic_id", "text"), ("score", "real"),
            ("is_primary", "boolean"),
        ],
        "works_keywords": [
            ("work_id", "text"), ("keyword_id", "text"), ("score", "real"),
        ],
        "works_concepts": [
            ("work_id", "text"), ("concept_id", "text"), ("score", "real"),
        ],
        "works_sdgs": [
            ("work_id", "text"), ("sdg_id", "text"),
            ("display_name", "text"), ("score", "real"),
        ],
        "works_mesh": [
            ("work_id", "text"), ("descriptor_ui", "text"),
            ("descriptor_name", "text"), ("qualifier_ui", "text"),
            ("qualifier_name", "text"), ("is_major_topic", "boolean"),
        ],
        "works_grants": [
            ("work_id", "text"), ("funder_id", "text"),
            ("funder_display_name", "text"), ("award_id", "text"),
        ],
        "works_awards": [
            ("work_id", "text"), ("award_id", "text"),
        ],
        "works_referenced_works": [
            ("work_id", "text"), ("referenced_work_id", "text"),
        ],
        "works_related_works": [
            ("work_id", "text"), ("related_work_id", "text"),
        ],
        "works_counts_by_year": [
            ("work_id", "text"), ("year", "integer"),
            ("cited_by_count", "bigint"),
        ],
    },
}

# ----------------------------------------------------------------------------
# extractors: one per entity, record -> {table: [row_dict, ...]}
# Every row_dict's keys must match the column names in TABLES.
# ----------------------------------------------------------------------------


def extract_domains(d):
    return {"domains": [{
        "id": d["id"], "display_name": d.get("display_name"),
        "description": d.get("description"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}


def extract_fields(d):
    return {"fields": [{
        "id": d["id"], "display_name": d.get("display_name"),
        "description": d.get("description"),
        "domain_id": (d.get("domain") or {}).get("id"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}


def extract_subfields(d):
    return {"subfields": [{
        "id": d["id"], "display_name": d.get("display_name"),
        "description": d.get("description"),
        "field_id": (d.get("field") or {}).get("id"),
        "domain_id": (d.get("domain") or {}).get("id"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}


def extract_topics(d):
    sub, fld, dom = d.get("subfield") or {}, d.get("field") or {}, d.get("domain") or {}
    return {"topics": [{
        "id": d["id"], "display_name": d.get("display_name"),
        "description": d.get("description"),
        "keywords": j(d.get("keywords")),
        "subfield_id": sub.get("id"),
        "subfield_display_name": sub.get("display_name"),
        "field_id": fld.get("id"), "field_display_name": fld.get("display_name"),
        "domain_id": dom.get("id"), "domain_display_name": dom.get("display_name"),
        "wikipedia_id": (d.get("ids") or {}).get("wikipedia"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "works_api_url": d.get("works_api_url"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}


def extract_keywords(d):
    return {"keywords": [{
        "id": d["id"], "display_name": d.get("display_name"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}


def extract_concepts(d):
    cid = d["id"]
    out = {"concepts": [{
        "id": cid, "wikidata": d.get("wikidata"),
        "display_name": d.get("display_name"), "level": d.get("level"),
        "description": d.get("description"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "image_url": d.get("image_url"),
        "image_thumbnail_url": d.get("image_thumbnail_url"),
        "works_api_url": d.get("works_api_url"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["concepts_ids"] = [{
            "concept_id": cid, "openalex": ids.get("openalex"),
            "wikidata": ids.get("wikidata"), "wikipedia": ids.get("wikipedia"),
            "umls_aui": j(ids.get("umls_aui")), "umls_cui": j(ids.get("umls_cui")),
            "mag": ids.get("mag"),
        }]
    out["concepts_ancestors"] = [
        {"concept_id": cid, "ancestor_id": a["id"]}
        for a in (d.get("ancestors") or []) if a.get("id")
    ]
    out["concepts_related_concepts"] = [
        {"concept_id": cid, "related_concept_id": r["id"], "score": r.get("score")}
        for r in (d.get("related_concepts") or []) if r.get("id")
    ]
    out["concepts_counts_by_year"] = [
        {"concept_id": cid, "year": c.get("year"),
         "works_count": c.get("works_count"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    return out


def extract_institutions(d):
    iid = d["id"]
    m2, h, i10 = stats(d)
    out = {"institutions": [{
        "id": iid, "ror": d.get("ror"), "display_name": d.get("display_name"),
        "country_code": d.get("country_code"), "type": d.get("type"),
        "type_id": d.get("type_id"), "lineage": j(d.get("lineage")),
        "is_super_system": d.get("is_super_system"),
        "homepage_url": d.get("homepage_url"), "image_url": d.get("image_url"),
        "image_thumbnail_url": d.get("image_thumbnail_url"),
        "display_name_acronyms": j(d.get("display_name_acronyms")),
        "display_name_alternatives": j(d.get("display_name_alternatives")),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "mean_citedness_2yr": m2, "h_index": h, "i10_index": i10,
        "status": d.get("status"), "works_api_url": d.get("works_api_url"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["institutions_ids"] = [{
            "institution_id": iid, "openalex": ids.get("openalex"),
            "ror": ids.get("ror"), "grid": ids.get("grid"),
            "wikipedia": ids.get("wikipedia"), "wikidata": ids.get("wikidata"),
            "mag": ids.get("mag"),
        }]
    geo = d.get("geo")
    if geo:
        out["institutions_geo"] = [{
            "institution_id": iid, "city": geo.get("city"),
            "geonames_city_id": geo.get("geonames_city_id"),
            "region": geo.get("region"),
            "country_code": geo.get("country_code"),
            "country": geo.get("country"), "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),
        }]
    out["institutions_associated_institutions"] = [
        {"institution_id": iid, "associated_institution_id": a["id"],
         "relationship": a.get("relationship")}
        for a in (d.get("associated_institutions") or []) if a.get("id")
    ]
    out["institutions_counts_by_year"] = [
        {"institution_id": iid, "year": c.get("year"),
         "works_count": c.get("works_count"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    out["institutions_roles"] = [
        {"institution_id": iid, "role": r.get("role"), "role_id": r.get("id"),
         "works_count": r.get("works_count")}
        for r in (d.get("roles") or [])
    ]
    out["institutions_repositories"] = [
        {"institution_id": iid, "repository_id": r.get("id"),
         "display_name": r.get("display_name")}
        for r in (d.get("repositories") or []) if r.get("id")
    ]
    return out


def extract_sources(d):
    sid = d["id"]
    m2, h, i10 = stats(d)
    out = {"sources": [{
        "id": sid, "issn_l": d.get("issn_l"), "issn": j(d.get("issn")),
        "display_name": d.get("display_name"),
        "host_organization": d.get("host_organization"),
        "host_organization_name": d.get("host_organization_name"),
        "host_organization_lineage": j(d.get("host_organization_lineage")),
        "works_count": d.get("works_count"),
        "oa_works_count": d.get("oa_works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "mean_citedness_2yr": m2, "h_index": h, "i10_index": i10,
        "is_oa": d.get("is_oa"), "is_in_doaj": d.get("is_in_doaj"),
        "is_in_scielo": d.get("is_in_scielo"), "is_core": d.get("is_core"),
        "is_ojs": d.get("is_ojs"), "is_high_oa_rate": d.get("is_high_oa_rate"),
        "oa_flip_year": d.get("oa_flip_year"), "type": d.get("type"),
        "apc_usd": d.get("apc_usd"), "country_code": d.get("country_code"),
        "homepage_url": d.get("homepage_url"),
        "first_publication_year": d.get("first_publication_year"),
        "last_publication_year": d.get("last_publication_year"),
        "alternate_titles": j(d.get("alternate_titles")),
        "societies": j(d.get("societies")),
        "apc_prices": j(d.get("apc_prices")),
        "works_api_url": d.get("works_api_url"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["sources_ids"] = [{
            "source_id": sid, "openalex": ids.get("openalex"),
            "issn_l": ids.get("issn_l"), "issn": j(ids.get("issn")),
            "mag": ids.get("mag"), "wikidata": ids.get("wikidata"),
            "fatcat": ids.get("fatcat"),
        }]
    out["sources_counts_by_year"] = [
        {"source_id": sid, "year": c.get("year"),
         "works_count": c.get("works_count"),
         "oa_works_count": c.get("oa_works_count"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    return out


def extract_publishers(d):
    pid = d["id"]
    m2, h, i10 = stats(d)
    out = {"publishers": [{
        "id": pid, "display_name": d.get("display_name"),
        "alternate_titles": j(d.get("alternate_titles")),
        "country_codes": j(d.get("country_codes")),
        "hierarchy_level": d.get("hierarchy_level"),
        "parent_publisher": d.get("parent_publisher"),
        "lineage": j(d.get("lineage")), "homepage_url": d.get("homepage_url"),
        "image_url": d.get("image_url"),
        "image_thumbnail_url": d.get("image_thumbnail_url"),
        "ror_id": d.get("ror_id"), "wikidata_id": d.get("wikidata_id"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "mean_citedness_2yr": m2, "h_index": h, "i10_index": i10,
        "sources_api_url": d.get("sources_api_url"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["publishers_ids"] = [{
            "publisher_id": pid, "openalex": ids.get("openalex"),
            "ror": ids.get("ror"), "wikidata": ids.get("wikidata"),
        }]
    out["publishers_counts_by_year"] = [
        {"publisher_id": pid, "year": c.get("year"),
         "works_count": c.get("works_count"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    out["publishers_roles"] = [
        {"publisher_id": pid, "role": r.get("role"), "role_id": r.get("id"),
         "works_count": r.get("works_count")}
        for r in (d.get("roles") or [])
    ]
    return out


def extract_funders(d):
    fid = d["id"]
    m2, h, i10 = stats(d)
    out = {"funders": [{
        "id": fid, "display_name": d.get("display_name"),
        "alternate_titles": j(d.get("alternate_titles")),
        "country_code": d.get("country_code"),
        "description": d.get("description"),
        "homepage_url": d.get("homepage_url"), "image_url": d.get("image_url"),
        "image_thumbnail_url": d.get("image_thumbnail_url"),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "awards_count": d.get("awards_count"),
        "mean_citedness_2yr": m2, "h_index": h, "i10_index": i10,
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["funders_ids"] = [{
            "funder_id": fid, "openalex": ids.get("openalex"),
            "ror": ids.get("ror"), "wikidata": ids.get("wikidata"),
            "crossref": ids.get("crossref"), "doi": ids.get("doi"),
        }]
    out["funders_counts_by_year"] = [
        {"funder_id": fid, "year": c.get("year"),
         "works_count": c.get("works_count"),
         "oa_works_count": c.get("oa_works_count"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    out["funders_roles"] = [
        {"funder_id": fid, "role": r.get("role"), "role_id": r.get("id"),
         "works_count": r.get("works_count")}
        for r in (d.get("roles") or [])
    ]
    return out


def extract_authors(d):
    aid = d["id"]
    m2, h, i10 = stats(d)
    out = {"authors": [{
        "id": aid, "orcid": d.get("orcid"),
        "display_name": d.get("display_name"),
        "display_name_alternatives": j(d.get("display_name_alternatives")),
        "works_count": d.get("works_count"),
        "cited_by_count": d.get("cited_by_count"),
        "mean_citedness_2yr": m2, "h_index": h, "i10_index": i10,
        "works_api_url": d.get("works_api_url"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["authors_ids"] = [{
            "author_id": aid, "openalex": ids.get("openalex"),
            "orcid": ids.get("orcid"), "scopus": ids.get("scopus"),
            "twitter": ids.get("twitter"), "wikipedia": ids.get("wikipedia"),
            "mag": ids.get("mag"),
        }]
    out["authors_counts_by_year"] = [
        {"author_id": aid, "year": c.get("year"),
         "works_count": c.get("works_count"),
         "oa_works_count": c.get("oa_works_count"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    out["authors_last_known_institutions"] = [
        {"author_id": aid, "institution_id": k["id"]}
        for k in (d.get("last_known_institutions") or []) if k.get("id")
    ]
    out["authors_affiliations"] = [
        {"author_id": aid, "institution_id": (a.get("institution") or {}).get("id"),
         "years": j(a.get("years"))}
        for a in (d.get("affiliations") or [])
        if (a.get("institution") or {}).get("id")
    ]
    out["authors_topics"] = [
        {"author_id": aid, "topic_id": t["id"], "count": t.get("count"),
         "score": t.get("value") if t.get("value") is not None else t.get("score")}
        for t in (d.get("topics") or []) if t.get("id")
    ]
    return out


def extract_awards(d):
    gid = d["id"]
    fr = d.get("funder") or {}
    out = {"awards": [{
        "id": gid, "display_name": d.get("display_name"),
        "description": d.get("description"),
        "funder_award_id": d.get("funder_award_id"),
        "amount": d.get("amount"), "currency": d.get("currency"),
        "funder_id": fr.get("id"),
        "funder_display_name": fr.get("display_name"),
        "funder_ror_id": fr.get("ror_id"), "funder_doi": fr.get("doi"),
        "funding_type": d.get("funding_type"),
        "funder_scheme": d.get("funder_scheme"),
        "provenance": d.get("provenance"),
        "start_date": d.get("start_date"), "end_date": d.get("end_date"),
        "start_year": d.get("start_year"), "end_year": d.get("end_year"),
        "landing_page_url": d.get("landing_page_url"), "doi": d.get("doi"),
        "works_api_url": d.get("works_api_url"),
        "funded_outputs_count": d.get("funded_outputs_count"),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    invs = []

    def add_inv(role, person):
        if not person:
            return
        aff = person.get("affiliation") or {}
        invs.append({
            "award_id": gid, "role": role,
            "given_name": person.get("given_name"),
            "family_name": person.get("family_name"),
            "orcid": person.get("orcid"),
            "affiliation_name": aff.get("name"),
            "affiliation_country": aff.get("country"),
        })

    add_inv("lead", d.get("lead_investigator"))
    add_inv("co_lead", d.get("co_lead_investigator"))
    for p in (d.get("investigators") or []):
        add_inv("investigator", p)
    out["awards_investigators"] = invs
    return out


def extract_works(d):
    wid = d["id"]
    cbp = d.get("cited_by_percentile_year") or {}
    cnp = d.get("citation_normalized_percentile") or {}
    pt = d.get("primary_topic") or {}
    pl = d.get("primary_location") or {}
    out = {"works": [{
        "id": wid, "doi": d.get("doi"), "title": d.get("title"),
        "display_name": d.get("display_name"),
        "publication_year": d.get("publication_year"),
        "publication_date": d.get("publication_date"),
        "language": d.get("language"), "type": d.get("type"),
        "countries_distinct_count": d.get("countries_distinct_count"),
        "institutions_distinct_count": d.get("institutions_distinct_count"),
        "authors_count": d.get("authors_count"),
        "locations_count": d.get("locations_count"),
        "referenced_works_count": d.get("referenced_works_count"),
        "fwci": d.get("fwci"), "has_fulltext": d.get("has_fulltext"),
        "has_content": j(d.get("has_content")),
        "is_retracted": d.get("is_retracted"),
        "is_paratext": d.get("is_paratext"), "is_xpac": d.get("is_xpac"),
        "cited_by_count": d.get("cited_by_count"),
        "cited_by_percentile_year_min": cbp.get("min"),
        "cited_by_percentile_year_max": cbp.get("max"),
        "citation_normalized_percentile": cnp.get("value"),
        "is_in_top_1_percent": cnp.get("is_in_top_1_percent"),
        "is_in_top_10_percent": cnp.get("is_in_top_10_percent"),
        "primary_topic_id": pt.get("id"),
        "primary_location_source_id": (pl.get("source") or {}).get("id"),
        "indexed_in": j(d.get("indexed_in")),
        "apc_list": j(d.get("apc_list")), "apc_paid": j(d.get("apc_paid")),
        "abstract_inverted_index": j(d.get("abstract_inverted_index")),
        "updated_date": d.get("updated_date"),
        "created_date": d.get("created_date"),
    }]}
    ids = d.get("ids")
    if ids:
        out["works_ids"] = [{
            "work_id": wid, "openalex": ids.get("openalex"),
            "doi": ids.get("doi"), "mag": ids.get("mag"),
            "pmid": ids.get("pmid"), "pmcid": ids.get("pmcid"),
        }]
    # locations (+ flag the primary / best-oa ones by identity match)
    best = d.get("best_oa_location")
    locs = []
    for pos, loc in enumerate(d.get("locations") or []):
        src = loc.get("source") or {}
        locs.append({
            "work_id": wid, "location_position": pos,
            "is_primary": loc == pl, "is_best_oa": loc == best,
            "source_id": src.get("id"),
            "landing_page_url": loc.get("landing_page_url"),
            "pdf_url": loc.get("pdf_url"), "is_oa": loc.get("is_oa"),
            "version": loc.get("version"), "license": loc.get("license"),
            "license_id": loc.get("license_id"),
            "is_published": loc.get("is_published"),
            "is_accepted": loc.get("is_accepted"),
            "raw_source_name": loc.get("raw_source_name"),
            "provenance": loc.get("provenance"),
        })
    out["works_locations"] = locs
    oa = d.get("open_access")
    if oa:
        out["works_open_access"] = [{
            "work_id": wid, "is_oa": oa.get("is_oa"),
            "oa_status": oa.get("oa_status"), "oa_url": oa.get("oa_url"),
            "any_repository_has_fulltext": oa.get("any_repository_has_fulltext"),
        }]
    # authorships
    auths, auth_insts, auth_countries = [], [], []
    for a in (d.get("authorships") or []):
        author_id = (a.get("author") or {}).get("id")
        if not author_id:
            continue
        auths.append({
            "work_id": wid, "author_position": a.get("author_position"),
            "author_id": author_id,
            "author_display_name": (a.get("author") or {}).get("display_name"),
            "raw_author_name": a.get("raw_author_name"),
            "is_corresponding": a.get("is_corresponding"),
        })
        for inst in (a.get("institutions") or []):
            if inst.get("id"):
                auth_insts.append({
                    "work_id": wid, "author_id": author_id,
                    "institution_id": inst["id"],
                })
        for cc in (a.get("countries") or []):
            auth_countries.append({
                "work_id": wid, "author_id": author_id, "country_code": cc,
            })
    out["works_authorships"] = auths
    out["works_authorship_institutions"] = auth_insts
    out["works_authorship_countries"] = auth_countries
    biblio = d.get("biblio")
    if biblio:
        out["works_biblio"] = [{
            "work_id": wid, "volume": biblio.get("volume"),
            "issue": biblio.get("issue"),
            "first_page": biblio.get("first_page"),
            "last_page": biblio.get("last_page"),
        }]
    primary_topic_id = pt.get("id")
    out["works_topics"] = [
        {"work_id": wid, "topic_id": t["id"], "score": t.get("score"),
         "is_primary": t["id"] == primary_topic_id}
        for t in (d.get("topics") or []) if t.get("id")
    ]
    out["works_keywords"] = [
        {"work_id": wid, "keyword_id": k["id"], "score": k.get("score")}
        for k in (d.get("keywords") or []) if k.get("id")
    ]
    out["works_concepts"] = [
        {"work_id": wid, "concept_id": c["id"], "score": c.get("score")}
        for c in (d.get("concepts") or []) if c.get("id")
    ]
    out["works_sdgs"] = [
        {"work_id": wid, "sdg_id": s.get("id"),
         "display_name": s.get("display_name"), "score": s.get("score")}
        for s in (d.get("sustainable_development_goals") or [])
    ]
    out["works_mesh"] = [
        {"work_id": wid, "descriptor_ui": m.get("descriptor_ui"),
         "descriptor_name": m.get("descriptor_name"),
         "qualifier_ui": m.get("qualifier_ui"),
         "qualifier_name": m.get("qualifier_name"),
         "is_major_topic": m.get("is_major_topic")}
        for m in (d.get("mesh") or [])
    ]
    out["works_grants"] = [
        {"work_id": wid, "funder_id": g.get("funder"),
         "funder_display_name": g.get("funder_display_name"),
         "award_id": g.get("award_id")}
        for g in (d.get("grants") or [])
    ]
    awards = []
    for aw in (d.get("awards") or []):
        award_id = aw.get("id") if isinstance(aw, dict) else aw
        if award_id:
            awards.append({"work_id": wid, "award_id": award_id})
    out["works_awards"] = awards
    out["works_referenced_works"] = [
        {"work_id": wid, "referenced_work_id": r}
        for r in (d.get("referenced_works") or []) if r
    ]
    out["works_related_works"] = [
        {"work_id": wid, "related_work_id": r}
        for r in (d.get("related_works") or []) if r
    ]
    out["works_counts_by_year"] = [
        {"work_id": wid, "year": c.get("year"),
         "cited_by_count": c.get("cited_by_count")}
        for c in (d.get("counts_by_year") or [])
    ]
    return out


EXTRACTORS = {
    "domains": extract_domains,
    "fields": extract_fields,
    "subfields": extract_subfields,
    "topics": extract_topics,
    "keywords": extract_keywords,
    "concepts": extract_concepts,
    "institutions": extract_institutions,
    "sources": extract_sources,
    "publishers": extract_publishers,
    "funders": extract_funders,
    "authors": extract_authors,
    "awards": extract_awards,
    "works": extract_works,
}

# Primary keys / important indexes, created *after* the bulk load.
# entity -> table -> ("pk", [cols]) | ("idx", [cols])
POST_LOAD_INDEXES = {
    "domains": {"domains": [("pk", ["id"])]},
    "fields": {"fields": [("pk", ["id"]), ("idx", ["domain_id"])]},
    "subfields": {"subfields": [("pk", ["id"]), ("idx", ["field_id"])]},
    "topics": {"topics": [("pk", ["id"]), ("idx", ["subfield_id"]),
                          ("idx", ["field_id"]), ("idx", ["domain_id"])]},
    "keywords": {"keywords": [("pk", ["id"])]},
    "concepts": {
        "concepts": [("pk", ["id"])],
        "concepts_ids": [("pk", ["concept_id"])],
        "concepts_ancestors": [("idx", ["concept_id"]), ("idx", ["ancestor_id"])],
        "concepts_related_concepts": [("idx", ["concept_id"])],
        "concepts_counts_by_year": [("pk", ["concept_id", "year"])],
    },
    "institutions": {
        "institutions": [("pk", ["id"]), ("idx", ["ror"]),
                         ("idx", ["country_code"])],
        "institutions_ids": [("pk", ["institution_id"])],
        "institutions_geo": [("pk", ["institution_id"])],
        "institutions_associated_institutions": [("idx", ["institution_id"])],
        "institutions_counts_by_year": [("pk", ["institution_id", "year"])],
        "institutions_roles": [("idx", ["institution_id"])],
        "institutions_repositories": [("idx", ["institution_id"])],
    },
    "sources": {
        "sources": [("pk", ["id"]), ("idx", ["issn_l"]),
                    ("idx", ["host_organization"]), ("idx", ["type"])],
        "sources_ids": [("pk", ["source_id"])],
        "sources_counts_by_year": [("pk", ["source_id", "year"])],
    },
    "publishers": {
        "publishers": [("pk", ["id"]), ("idx", ["parent_publisher"])],
        "publishers_ids": [("pk", ["publisher_id"])],
        "publishers_counts_by_year": [("pk", ["publisher_id", "year"])],
        "publishers_roles": [("idx", ["publisher_id"])],
    },
    "funders": {
        "funders": [("pk", ["id"])],
        "funders_ids": [("pk", ["funder_id"])],
        "funders_counts_by_year": [("pk", ["funder_id", "year"])],
        "funders_roles": [("idx", ["funder_id"])],
    },
    "authors": {
        "authors": [("pk", ["id"]), ("idx", ["orcid"])],
        "authors_ids": [("pk", ["author_id"])],
        "authors_counts_by_year": [("pk", ["author_id", "year"])],
        "authors_last_known_institutions": [("idx", ["author_id"]),
                                            ("idx", ["institution_id"])],
        "authors_affiliations": [("idx", ["author_id"]),
                                 ("idx", ["institution_id"])],
        "authors_topics": [("idx", ["author_id"]), ("idx", ["topic_id"])],
    },
    "awards": {
        "awards": [("pk", ["id"]), ("idx", ["funder_id"])],
        "awards_investigators": [("idx", ["award_id"])],
    },
    "works": {
        "works": [("pk", ["id"]), ("idx", ["doi"]),
                  ("idx", ["publication_year"]), ("idx", ["type"]),
                  ("idx", ["primary_topic_id"]),
                  ("idx", ["primary_location_source_id"])],
        "works_ids": [("pk", ["work_id"]), ("idx", ["pmid"])],
        "works_locations": [("idx", ["work_id"]), ("idx", ["source_id"])],
        "works_open_access": [("pk", ["work_id"])],
        "works_authorships": [("idx", ["work_id"]), ("idx", ["author_id"])],
        "works_authorship_institutions": [("idx", ["work_id"]),
                                          ("idx", ["author_id"]),
                                          ("idx", ["institution_id"])],
        "works_authorship_countries": [("idx", ["work_id"]),
                                       ("idx", ["author_id"])],
        "works_biblio": [("pk", ["work_id"])],
        "works_topics": [("idx", ["work_id"]), ("idx", ["topic_id"])],
        "works_keywords": [("idx", ["work_id"]), ("idx", ["keyword_id"])],
        "works_concepts": [("idx", ["work_id"]), ("idx", ["concept_id"])],
        "works_sdgs": [("idx", ["work_id"])],
        "works_mesh": [("idx", ["work_id"])],
        "works_grants": [("idx", ["work_id"]), ("idx", ["funder_id"])],
        "works_awards": [("idx", ["work_id"]), ("idx", ["award_id"])],
        "works_referenced_works": [("idx", ["work_id"]),
                                   ("idx", ["referenced_work_id"])],
        "works_related_works": [("idx", ["work_id"])],
        "works_counts_by_year": [("idx", ["work_id"])],
    },
}
