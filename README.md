# OpenAlex API Examples

Python snippets for exploring 240M+ scholarly works via the [OpenAlex](https://openalex.org/) API.

**Website**: [https://simonesantoni.github.io/openalex/](https://simonesantoni.github.io/openalex/)

## What's here

- **API Reference** — entities, filters, search, pagination, and credit costs
- **Topic Search** — four-level taxonomy (Domain → Field → Subfield → Topic) + CLI tool
- **Example Notebook** — querying `/subfields` and `/works` endpoints with matplotlib visualizations

## Quick start

```bash
git clone https://github.com/simoneSantoni/openalex.git
cd openalex

python -m venv .venv && source .venv/bin/activate
pip install httpx pandas matplotlib requests python-dotenv

# render the site
quarto render

# run the CLI tool
python topicSearch/get_subfields.py --list
python topicSearch/get_subfields.py "Computer Science"
```

## License

MIT License — Simone Santoni
