# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A working repository of notes, examples, and tools for OpenAlex — a free, open
catalog of 240M+ scholarly works. It is for the maintainer's and collaborators'
own use; it is **not** a published website.

The repo is organized around the **two ways to access OpenAlex**, mirrored by
two top-level directories:

- `api/` — working with the live OpenAlex REST API (reference, topic taxonomy, a worked example, the CLI tool)
- `datadump/` — working with the bulk OpenAlex S3 snapshot (currently a scaffold, content in progress)

## Layout

- `README.md` — project overview, setup, OpenAlex essentials, and an annotated 50-field sample Work record
- `api/README.md` — index of the API arm
- `api/api-reference.md` — API quick reference (entities, filters, search, pagination, credit costs)
- `api/topic-search.md` — topic taxonomy notes + `get_subfields.py` CLI reference
- `api/exploring-subfields.md` — worked example: querying `/subfields` and `/works`, then charting work counts
- `api/get_subfields.py` — standalone CLI tool (uses `requests`, no API key needed): lists OpenAlex fields and retrieves a field's subfields by name (search) or numeric ID
- `api/data/` — the 15 CSVs produced by the `exploring-subfields` example (committed, force-added past the `data/` pattern in `.gitignore`)
- `datadump/README.md` — overview of the bulk S3 snapshot (scaffold; sections are TODO outlines)

Everything is plain Markdown and Python — there is no build step and no site
generator. (The repo was previously a Quarto website; that infrastructure has
been removed.)

## Commands

```bash
# Run the CLI tool (field name or numeric field ID)
python api/get_subfields.py --list
python api/get_subfields.py "Computer Science"
python api/get_subfields.py 17
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx pandas matplotlib requests python-dotenv tqdm
```

The CLI tool needs no API key. The `exploring-subfields.md` worked example needs
one only to *refresh* its data — create a `.env` at the repo root:

```bash
OPENALEX_API_KEY=your_key_here
OPENALEX_MAILTO=your_email   # optional, for the polite pool
```

## The exploring-subfields workflow

`api/exploring-subfields.md` documents a two-phase data flow:

1. **Fetch + save** — query `/subfields` and `/works` (with `httpx.Client`, retry-on-429) and write 15 CSVs to `api/data/` (per-field + combined files for subfields, works-by-year, works-by-source). Run this manually when data needs refreshing.
2. **Analysis** — read the combined CSVs back with `pd.read_csv()` and produce matplotlib charts.

The CSVs in `api/data/` are committed so the example is reproducible without an API key.

## OpenAlex API Essentials

- **Base URL**: `https://api.openalex.org`
- **Auth**: free API key as `?api_key=YOUR_KEY`; `mailto` param for the polite pool
- **Rate limits**: 100,000 credits/day, max 100 req/s
- **Credit costs**: single entity = 0, list = 1, search = 10, semantic search = 1,000
- **Entities**: Works, Authors, Sources, Institutions, Topics, Publishers, Funders
- **Topic hierarchy**: Domain (4) → Field (26) → Subfield (200) → Topic (~4,500)
- **Cursor paging** for >10K results: `?cursor=*`, follow `next_cursor`
- **Filter operators**: AND (comma), OR (pipe), NOT (`!`), inequality (`<`/`>`)
- Note: list endpoints accept `per-page` (hyphen) as a query param.

## Key Libraries

- `httpx` — HTTP client in the worked example (`httpx.Client` for connection pooling + retry on 429)
- `requests` — used by the CLI tool
- `pandas` + `matplotlib` — data wrangling and visualization
- `python-dotenv` — loads `.env` for API key/mailto
- `tqdm` — progress bars in the fetch loop
