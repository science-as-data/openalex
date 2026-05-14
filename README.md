# OpenAlex

Notes, examples, and tools for working with [OpenAlex](https://openalex.org/) —
a free, open catalog of the world's scholarly research (240 M+ works: journal
articles, books, datasets, theses; updated daily).

This is a working repo for my own and collaborators' use, not a published site.
It is organized around the **two ways to access OpenAlex**:

- [`api/`](api/) — the live REST API: lookups, filtered lists, search, the topic
  taxonomy, and a CLI tool.
- [`datadump/`](datadump/) — the bulk S3 snapshot: downloading and querying the
  full catalog locally (scaffold, in progress).

## Contents

### `api/` — the live REST API

- [api/api-reference.md](api/api-reference.md) — entities, filters, search, pagination, credit costs
- [api/topic-search.md](api/topic-search.md) — four-level taxonomy (Domain → Field → Subfield → Topic) + the `get_subfields.py` CLI
- [api/exploring-subfields.md](api/exploring-subfields.md) — worked example: querying `/subfields` and `/works` with matplotlib charts
- [api/get_subfields.py](api/get_subfields.py) — CLI: list fields, retrieve a field's subfields
- [api/data/](api/data/) — the 15 CSVs produced by the worked example

### `datadump/` — the bulk S3 snapshot

- [datadump/README.md](datadump/README.md) — what the dump contains, how to download it, on-disk layout (scaffold)

## Setup

```bash
git clone https://github.com/science-as-data/openalex.git
cd openalex

python -m venv .venv && source .venv/bin/activate
pip install httpx pandas matplotlib requests python-dotenv tqdm

# run the CLI tool (no API key needed)
python api/get_subfields.py --list
python api/get_subfields.py "Computer Science"
```

The worked example in [api/exploring-subfields.md](api/exploring-subfields.md)
needs an API key to refresh its data. Create a `.env` at the repo root:

```bash
OPENALEX_API_KEY=your_key_here
OPENALEX_MAILTO=your_email   # optional, for the polite pool
```

## OpenAlex essentials

- **Base URL:** `https://api.openalex.org`
- **Auth:** free API key as `?api_key=YOUR_KEY`; `mailto` param for the polite pool
- **Rate limits:** 100,000 credits/day, max 100 req/s
- **Credit costs:** single entity = 0, list = 1, search = 10, semantic search = 1,000
- **Entities:** Works, Authors, Sources, Institutions, Topics, Publishers, Funders
- **Topic hierarchy:** Domain (4) → Field (26) → Subfield (200) → Topic (~4,500)
- **Cursor paging** for >10K results: `?cursor=*`, follow `next_cursor`
- **Filter operators:** AND (comma), OR (pipe), NOT (`!`), inequality (`<`/`>`)

## Sample record

Every work in OpenAlex is a richly structured JSON object with 50 top-level
fields. At its core you get **identity** information (OpenAlex ID, DOI, title)
and **publication metadata** (year, date, language, document type). The
**primary location** block tells you where the work was published — journal
name, ISSN, license, version — while the **open access** block summarises
whether it is freely available and through which route (gold, green, hybrid,
bronze, or closed).

**Authorship** data links each contributor to their ORCID, affiliated
institutions (with ROR IDs), and country codes, and flags the corresponding
author. **Citation metrics** include the raw count, field-weighted citation
impact (FWCI), normalised percentile rankings, and a year-by-year breakdown.
Each work is classified through the **four-level topic hierarchy** — domain,
field, subfield, topic — with confidence scores. The **abstract** is stored as
an inverted index (word → position list) to support full-text search without
redistributing copyrighted text.

Below is the full structure for `GET /works/W2741809807`, with arrays trimmed
to the first element:

```jsonc
{
  // ── Identity ──────────────────────────────────────────────────
  "id": "https://openalex.org/W2741809807",       // OpenAlex URI
  "doi": "https://doi.org/10.7717/peerj.4375",    // DOI as URL
  "title": "The state of OA: ...",                 // full title
  "display_name": "The state of OA: ...",          // same as title
  "ids": {                                         // cross-referenced IDs
    "openalex": "https://openalex.org/W2741809807",
    "doi": "https://doi.org/10.7717/peerj.4375",
    "mag": "2741809807",
    "pmid": "https://pubmed.ncbi.nlm.nih.gov/29456894"
  },

  // ── Publication metadata ──────────────────────────────────────
  "publication_year": 2018,
  "publication_date": "2018-02-13",
  "language": "en",                                // ISO 639-1 code
  "type": "book-chapter",                          // Crossref type
  "indexed_in": ["crossref", "doaj", "pubmed"],    // indexing databases

  // ── Primary location (where the work is published) ────────────
  "primary_location": {
    "is_oa": true,
    "landing_page_url": "https://doi.org/10.7717/peerj.4375",
    "pdf_url": null,
    "source": {
      "id": "https://openalex.org/S1983995261",
      "display_name": "PeerJ",
      "issn_l": "2167-8359",
      "is_oa": true,
      "is_in_doaj": true,
      "type": "journal"
    },
    "license": "cc-by",
    "version": "publishedVersion"
  },

  // ── Open Access status ────────────────────────────────────────
  "open_access": {
    "is_oa": true,
    "oa_status": "gold",                           // gold|green|hybrid|bronze|closed
    "oa_url": "https://doi.org/10.7717/peerj.4375",
    "any_repository_has_fulltext": true
  },

  // ── Authors & affiliations (9 authors, first shown) ───────────
  "authorships": [
    {
      "author_position": "first",                  // first|middle|last
      "author": {
        "id": "https://openalex.org/A5048491430",
        "display_name": "Heather Piwowar",
        "orcid": "https://orcid.org/0000-0003-1613-5981"
      },
      "institutions": [
        {
          "id": "https://openalex.org/I4210166736",
          "display_name": "Impact Technology Development (United States)",
          "ror": "https://ror.org/05ppvf150",
          "country_code": "US",
          "type": "company"
        }
      ],
      "countries": ["US"],
      "is_corresponding": true
    }
    // ... 8 more authors
  ],

  // ── Aggregate author/institution stats ────────────────────────
  "institutions": [],                              // deprecated; use authorships
  "countries_distinct_count": 2,
  "institutions_distinct_count": 9,
  "corresponding_author_ids": ["https://openalex.org/A5048491430"],
  "corresponding_institution_ids": ["https://openalex.org/I4210166736"],

  // ── Article processing charges ────────────────────────────────
  "apc_list": { "value": 1395, "currency": "USD", "value_usd": 1395 },
  "apc_paid": { "value": 1395, "currency": "USD", "value_usd": 1395 },

  // ── Citation metrics ──────────────────────────────────────────
  "fwci": 504.41,                                  // field-weighted citation impact
  "cited_by_count": 1149,
  "citation_normalized_percentile": {
    "value": 1.0,
    "is_in_top_1_percent": true,
    "is_in_top_10_percent": true
  },
  "cited_by_percentile_year": { "min": 99, "max": 100 },
  "counts_by_year": [                              // annual citation breakdown
    { "year": 2026, "cited_by_count": 17 },
    { "year": 2025, "cited_by_count": 133 }
    // ... more years
  ],

  // ── Bibliographic details ─────────────────────────────────────
  "biblio": {
    "volume": "6",
    "issue": null,
    "first_page": "e4375",
    "last_page": "e4375"
  },
  "has_fulltext": false,
  "is_retracted": false,
  "is_paratext": false,
  "is_xpac": false,

  // ── Topic classification (4-level hierarchy) ──────────────────
  "primary_topic": {                               // single best-matching topic
    "id": "https://openalex.org/T10102",
    "display_name": "scientometrics and bibliometrics research",
    "score": 0.9969,                               // confidence 0–1
    "subfield": { "display_name": "Statistics, Probability and Uncertainty" },
    "field":    { "display_name": "Decision Sciences" },
    "domain":   { "display_name": "Social Sciences" }
  },
  "topics": [                                      // additional high-scoring topics
    { "id": "...", "display_name": "...", "score": 0.98 }
    // ...
  ],

  // ── Keywords, concepts & subject tags ─────────────────────────
  "keywords": [
    { "id": "https://openalex.org/keywords/citation", "display_name": "Citation", "score": 0.69 }
    // ... more keywords
  ],
  "concepts": [                                    // legacy (deprecated); use topics
    { "id": "...", "display_name": "Citation", "level": 2, "score": 0.69 }
    // ...
  ],
  "mesh": [],                                      // MeSH terms (biomedical works)
  "sustainable_development_goals": [],             // UN SDG tags

  // ── All locations where the work appears ──────────────────────
  "locations_count": 6,
  "locations": [                                   // publisher, repositories, etc.
    { "is_oa": true, "source": { "display_name": "PeerJ" }, "version": "publishedVersion" }
    // ... 5 more locations
  ],
  "best_oa_location": { "..." : "same structure as primary_location" },

  // ── Funding & awards ──────────────────────────────────────────
  "awards": [],
  "funders": [],

  // ── Content availability ──────────────────────────────────────
  "has_content": { "grobid_xml": false, "pdf": false },
  "content_urls": null,

  // ── References & related works ────────────────────────────────
  "referenced_works_count": 54,
  "referenced_works": [                            // outgoing citations
    "https://openalex.org/W1560783210"
    // ... 53 more
  ],
  "related_works": [                               // algorithmically related
    "https://openalex.org/W2294604317"
    // ... more
  ],

  // ── Abstract (stored as inverted index) ───────────────────────
  "abstract_inverted_index": {                     // word → list of positions
    "Despite": [0], "growing": [1], "interest": [2]
    // ...
  },

  // ── Record timestamps ─────────────────────────────────────────
  "updated_date": "2026-02-16T07:36:33.822630",
  "created_date": "2025-10-10T00:00:00"
}
```

> On 2026-02-16 I gathered a data dump of OpenAlex via bulk download:
> `aws s3 sync "s3://openalex" "openalex-snapshot" --no-sign-request`.
> See [datadump/README.md](datadump/README.md).

## Links

- [OpenAlex](https://openalex.org/) — the platform
- [Official API docs](https://docs.openalex.org/) — full reference
- [Snapshot docs](https://docs.openalex.org/download-all-data/openalex-snapshot) — bulk download guide

## License

MIT License — Simone Santoni
