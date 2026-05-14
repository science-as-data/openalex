# Exploring Research Subfields with the OpenAlex API

This walkthrough uses the `/subfields` and `/works` endpoints to retrieve and
visualise the research subfields that make up four major academic fields:
Physics and Astronomy, Agricultural and Biological Sciences, Biochemistry,
Genetics and Molecular Biology, and Economics, Econometrics and Finance.

The code below is presented as documentation — copy it into a script or a
notebook to run it. It needs an API key in a `.env` file at the repo root
(`OPENALEX_API_KEY`, optionally `OPENALEX_MAILTO`). The fetch steps write 15
CSVs to `api/data/`; the analysis steps read those CSVs back and chart them.

## Setup

`FIELDS` maps each field name to its OpenAlex identifier. `get_subfields()`
queries the `/subfields` endpoint for a given field and returns the results as a
DataFrame with columns for the field name, subfield name, and work count.
`plot_subfields()` renders a horizontal bar chart from that DataFrame.

```python
import os
import time
import httpx
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.openalex.org"

api = httpx.Client(
    base_url=BASE_URL,
    params={
        "mailto": os.environ.get("OPENALEX_MAILTO", ""),
        "api_key": os.environ["OPENALEX_API_KEY"],
    },
    timeout=30,
)

FIELDS = {
    "Physics and Astronomy": "fields/31",
    "Agricultural and Biological Sciences": "fields/11",
    "Biochemistry, Genetics and Molecular Biology": "fields/13",
    "Economics, Econometrics and Finance": "fields/20",
}


def _get(path: str, **kwargs) -> dict:
    """GET with automatic retry on 429 and connection errors."""
    for attempt in range(5):
        try:
            r = api.get(path, **kwargs)
        except httpx.ReadError:
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Max retries exceeded")


def get_subfields(field_name: str, field_id: str) -> pd.DataFrame:
    data = _get("/subfields", params={
        "filter": f"field.id:{field_id}",
        "select": "id,display_name,works_count",
        "per-page": 50,
        "sort": "works_count:desc",
    })
    df = pd.DataFrame(data["results"])[["display_name", "works_count"]]
    df.columns = ["Subfield", "Works"]
    df.insert(0, "Field", field_name)
    return df


BAR_HEIGHT = 0.25  # inches per bar — keeps bars the same size across charts


def plot_subfields(df: pd.DataFrame):
    fig_h = max(2, len(df) * BAR_HEIGHT + 1)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    ax.barh(df["Subfield"][::-1], df["Works"][::-1], color="#9e9e9e")
    ax.set_xlabel("Number of works")
    ax.grid(axis="x", color="#b0bec5", linewidth=0.5, linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    plt.tight_layout()
    plt.show()


def get_works_by_year(field_name: str, field_id: str) -> pd.DataFrame:
    data = _get("/works", params={
        "filter": f"primary_topic.field.id:{field_id}",
        "group_by": "publication_year",
    })
    rows = [
        {"Year": int(g["key"]), "Works": g["count"]}
        for g in data["group_by"]
        if g["key"] != "unknown"
    ]
    df = pd.DataFrame(rows).sort_values("Year")
    df.insert(0, "Field", field_name)
    return df


def plot_works_by_year(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.fill_between(df["Year"], df["Works"], alpha=0.3, color="#e67e22")
    ax.plot(df["Year"], df["Works"], color="#e67e22", linewidth=1.5)
    ax.set_xlabel("Publication year")
    ax.set_ylabel("Number of works")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.grid(axis="y", color="#b0bec5", linewidth=0.5, linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    plt.tight_layout()
    plt.show()


def get_works_by_source(field_name: str, field_id: str) -> pd.DataFrame:
    params = {
        "filter": f"primary_topic.field.id:{field_id}",
        "group_by": "primary_location.source.id",
        "per-page": 200,
        "cursor": "*",
    }
    rows = []
    while True:
        data = _get("/works", params=params)
        for g in data["group_by"]:
            rows.append({"Source": g["key_display_name"], "Works": g["count"]})
        cursor = data["meta"].get("next_cursor")
        if not cursor or len(data["group_by"]) == 0:
            break
        params["cursor"] = cursor
        time.sleep(0.1)
    df = pd.DataFrame(rows).sort_values("Works", ascending=False).reset_index(drop=True)
    df.insert(0, "Field", field_name)
    return df


TOP_N_SOURCES = 20


def plot_works_by_source(df: pd.DataFrame):
    top = df.head(TOP_N_SOURCES)
    fig_h = max(2, len(top) * BAR_HEIGHT + 1)
    fig, ax = plt.subplots(figsize=(6, fig_h))
    ax.barh(top["Source"][::-1], top["Works"][::-1], color="#2980b9")
    ax.set_xlabel("Number of works")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.grid(axis="x", color="#b0bec5", linewidth=0.5, linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    plt.tight_layout()
    plt.show()
```

## Fetch data

Loop over the four fields and collect subfield breakdowns, yearly publication
counts, and top sources for each one.

```python
from tqdm.auto import tqdm

dfs = {}
yearly = {}
sources = {}
for name, fid in tqdm(FIELDS.items(), total=len(FIELDS), desc="Fields"):
    dfs[name] = get_subfields(name, fid)
    yearly[name] = get_works_by_year(name, fid)
    sources[name] = get_works_by_source(name, fid)
```

## Save to CSV

Persist all three datasets to the `data/` directory — one CSV per field plus a
combined file for each dataset (subfields, works-by-year, works-by-source),
giving 15 files in total. The combined files are what the field-level analysis
section reads back via `pd.read_csv()`.

```python
from pathlib import Path

data_dir = Path("data")
data_dir.mkdir(exist_ok=True)

for name, df in dfs.items():
    slug = name.lower().replace(", ", "-").replace(" ", "-")
    path = data_dir / f"subfields-{slug}.csv"
    df.to_csv(path, index=False)
    print(f"Saved {len(df):>2} rows to {path}")

all_subfields = pd.concat(dfs.values(), ignore_index=True)
path = data_dir / "subfields.csv"
all_subfields.to_csv(path, index=False)
print(f"Saved {len(all_subfields):>2} rows to {path} (combined)")

for name, df in yearly.items():
    slug = name.lower().replace(", ", "-").replace(" ", "-")
    path = data_dir / f"works-by-year-{slug}.csv"
    df.to_csv(path, index=False)
    print(f"Saved {len(df):>2} rows to {path}")

all_yearly = pd.concat(yearly.values(), ignore_index=True)
path = data_dir / "works-by-year.csv"
all_yearly.to_csv(path, index=False)
print(f"Saved {len(all_yearly):>2} rows to {path} (combined)")

for name, df in sources.items():
    slug = name.lower().replace(", ", "-").replace(" ", "-")
    path = data_dir / f"works-by-source-{slug}.csv"
    df.to_csv(path, index=False)
    print(f"Saved {len(df):>5,} rows to {path}")

all_sources = pd.concat(sources.values(), ignore_index=True)
path = data_dir / "works-by-source.csv"
all_sources.to_csv(path, index=False)
print(f"Saved {len(all_sources):>5,} rows to {path} (combined)")
```

## Field-level analysis

The visualisations below are driven by the CSV files saved in the previous
steps. Re-run the *Fetch data* and *Save to CSV* steps when you need to refresh
the underlying data.

```python
import pandas as pd
import matplotlib.pyplot as plt

all_subfields = pd.read_csv("data/subfields.csv")
all_yearly = pd.read_csv("data/works-by-year.csv")
all_sources = pd.read_csv("data/works-by-source.csv")

dfs = {name: g.reset_index(drop=True) for name, g in all_subfields.groupby("Field")}
yearly = {name: g.reset_index(drop=True) for name, g in all_yearly.groupby("Field")}
sources = {name: g.reset_index(drop=True) for name, g in all_sources.groupby("Field")}


def table_top_sources(df: pd.DataFrame):
    top = df.head(TOP_N_SOURCES)[["Source", "Works"]].copy()
    top.index = range(1, len(top) + 1)
    top.index.name = "Rank"
    top["Works"] = top["Works"].map("{:,}".format)
    print(top.to_markdown())


def plot_source_rank_freq(df: pd.DataFrame):
    rank = range(1, len(df) + 1)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.scatter(rank, df["Works"], s=12, alpha=0.4, facecolors="#8e44ad", edgecolors="#8e44ad", linewidths=0.5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Source rank")
    ax.set_ylabel("Number of works")
    ax.grid(True, which="major", color="#b0bec5", linewidth=0.5, linestyle="--")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    plt.tight_layout()
    plt.show()
```

For each field, the four views are: annual distribution of works, a top-sources
table, the rank–frequency distribution of sources (log–log), and the subfields
ranked by number of works.

```python
for field, entity in [
    ("Physics and Astronomy", "fields/31"),
    ("Agricultural and Biological Sciences", "fields/11"),
    ("Biochemistry, Genetics and Molecular Biology", "fields/13"),
    ("Economics, Econometrics and Finance", "fields/20"),
]:
    total = dfs[field]["Works"].sum()
    n_sources = len(sources[field])
    print(f"\n## {field}")
    print(f"OpenAlex entity: https://openalex.org/{entity} | "
          f"{total:,} total works | {n_sources:,} unique journals")

    plot_works_by_year(yearly[field])
    table_top_sources(sources[field])
    plot_source_rank_freq(sources[field])
    plot_subfields(dfs[field])
```
