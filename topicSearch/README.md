# Topic Search

## OpenAlex Topic Hierarchy

OpenAlex classifies every work into a **four-level taxonomy**, from broadest to most specific:

| Level        | Count | Example                              |
| ------------ | ----- | ------------------------------------ |
| **Domain**   | 4     | Physical Sciences                    |
| **Field**    | 26    | Physics and Astronomy                |
| **Subfield** | 200   | Nuclear and High Energy Physics      |
| **Topic**    | 4,516 | Magnetic confinement fusion research |

### The 4 Domains

| Domain            | Topics |
| ----------------- | ------ |
| Physical Sciences | 1,571  |
| Social Sciences   | 1,487  |
| Health Sciences   | 844    |
| Life Sciences     | 614    |

## How Topics Are Assigned to Works

OpenAlex uses an automated classifier that scores every work across all ~4,500 topics based on the work's **title, abstract, source (journal) name, and citations**.

- `primary_topic` — the single highest-scoring topic, including its `score` (0–1) and full hierarchy (subfield → field → domain)
- `topics` — a list of additional highly ranked topics, each with their own score and hierarchy

Example (abbreviated):

```json
{
  "primary_topic": {
    "id": "https://openalex.org/T10346",
    "display_name": "Magnetic confinement fusion research",
    "score": 0.9991,
    "subfield": { "display_name": "Nuclear and High Energy Physics" },
    "field":    { "display_name": "Physics and Astronomy" },
    "domain":   { "display_name": "Physical Sciences" }
  },
  "topics": [ ... ]  // additional high-scoring topics
}
```

## Topic Object Structure

Each topic entity (`/topics/{id}`) contains:

| Field            | Description                                       |
| ---------------- | ------------------------------------------------- |
| `id`             | OpenAlex URI (e.g. `https://openalex.org/T10346`) |
| `display_name`   | English-language label                            |
| `description`    | AI-generated summary of the paper cluster         |
| `keywords`       | AI-generated representative terms                 |
| `ids`            | External identifiers (OpenAlex, Wikipedia)        |
| `subfield`       | Parent subfield (`id` + `display_name`)           |
| `field`          | Parent field                                      |
| `domain`         | Parent domain                                     |
| `siblings`       | Other topics in the same subfield                 |
| `works_count`    | Number of works tagged with this topic            |
| `cited_by_count` | Total citations across tagged works               |
| `works_api_url`  | API URL to retrieve works for this topic          |

## Useful API Queries

```bash
# List all topics
curl "https://api.openalex.org/topics"

# Search topics by name
curl "https://api.openalex.org/topics?search=machine+learning"

# Get topics grouped by domain
curl "https://api.openalex.org/topics?group_by=domain.id"

# Filter works by a specific topic
curl "https://api.openalex.org/works?filter=topics.id:T10346"

# Filter works by primary topic only
curl "https://api.openalex.org/works?filter=primary_topic.id:T10346"

# Filter works by subfield
curl "https://api.openalex.org/works?filter=primary_topic.subfield.id:3106"
```

## References

- [OpenAlex Topics docs](https://docs.openalex.org/api-entities/topics)
- [Topic object reference](https://docs.openalex.org/api-entities/topics/topic-object)
- Paper: _OpenAlex: End-to-End Process for Topic Classification_
