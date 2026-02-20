# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Quarto website containing Python examples and documentation for the OpenAlex API — a free, open catalog of 240M+ scholarly works. The primary data source for examples is the OpenAlex data dump (not the API), though API snippets are included for quick lookups.

## Build Commands

```bash
# Render the full site (outputs to _site/)
quarto render

# Preview with live reload
quarto preview

# Render a single page
quarto render examples/exploring-subfields.qmd

# Run the CLI tool
python topicSearch/get_subfields.py --list
python topicSearch/get_subfields.py "Computer Science"
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install httpx pandas matplotlib requests python-dotenv
```

The executable notebook (`examples/exploring-subfields.qmd`) requires an `OPENALEX_API_KEY` environment variable. Create a `.env` file at the project root:

```bash
OPENALEX_API_KEY=your_key_here
```

## Architecture

**Quarto website** (`_quarto.yml`) with four pages:

- `index.qmd` — landing page with project overview and annotated sample record
- `api-reference.qmd` — API quick reference (entities, filters, search, pagination, credit costs)
- `topic-search.qmd` — topic taxonomy docs (Domain → Field → Subfield → Topic) + CLI tool reference
- `examples/exploring-subfields.qmd` — executable notebook querying `/subfields` and `/works` endpoints with matplotlib visualizations; outputs CSVs to `data/`

**CLI tool**: `topicSearch/get_subfields.py` — standalone script (uses `requests`, no API key needed) to list fields and retrieve subfields by name or numeric ID.

**Generated outputs**: `data/` directory (CSVs from notebook), `_site/` (rendered HTML). Both are gitignored.

**Quarto config**: `code-fold: true` globally (all code blocks collapsed by default), `cosmo` theme, TOC enabled on every page.

## OpenAlex API Essentials

- **Base URL**: `https://api.openalex.org`
- **Auth**: free API key passed as `?api_key=YOUR_KEY`; `mailto` param for polite pool (used in notebook via `httpx.Client`)
- **Rate limits**: 100,000 credits/day, max 100 req/s
- **Credit costs**: single entity = 0, list = 1, search = 10, semantic search = 1,000
- **Entities**: Works, Authors, Sources, Institutions, Topics, Publishers, Funders
- **Topic hierarchy**: Domain (4) → Field (26) → Subfield (200) → Topic (~4,500)
- **Cursor paging** for >10K results: `?cursor=*`, follow `next_cursor`
- **Filter operators**: AND (comma), OR (pipe), NOT (`!`), inequality (`<`/`>`)

## Key Libraries

- `httpx` — preferred HTTP client in notebooks (used with `httpx.Client` for connection pooling + retry on 429)
- `requests` — used in the CLI tool
- `pandas` + `matplotlib` — data wrangling and visualization
- `python-dotenv` — loads `.env` file for API key in notebooks
