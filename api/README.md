# API arm — the live OpenAlex REST API

Notes and tools for querying the live OpenAlex REST API: lookups, filtered
lists, and search.

## Contents

- [api-reference.md](api-reference.md) — entities, filters, search, sort, pagination, and credit costs
- [topic-search.md](topic-search.md) — the four-level taxonomy (Domain → Field → Subfield → Topic) and the `get_subfields.py` CLI
- [exploring-subfields.md](exploring-subfields.md) — a worked example: querying `/subfields` and `/works`, then charting work counts across four fields
- [get_subfields.py](get_subfields.py) — CLI tool: list OpenAlex fields and retrieve a field's subfields by name or numeric ID (uses `requests`, no API key needed)
- [data/](data/) — the 15 CSVs produced by the `exploring-subfields` example

## CLI quick start

```bash
python get_subfields.py --list                # list all 26 fields
python get_subfields.py "Computer Science"     # look up by name
python get_subfields.py 17                     # look up by numeric ID
```

## Essentials

- **Base URL:** `https://api.openalex.org`
- **Auth:** free API key as `?api_key=YOUR_KEY`; `mailto` param for the polite pool
- **Rate limits:** 100,000 credits/day, max 100 req/s
- **Credit costs:** single entity = 0, list = 1, search = 10, semantic search = 1,000

See [api-reference.md](api-reference.md) for the full reference.
