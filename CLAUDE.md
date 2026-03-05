# arxiv-personal-digest

A personal arXiv paper curation tool with a feedback loop. Each run fetches new papers in a configured field, uses an LLM to filter them against a preferences file, pushes relevant ones to a Notion database, and updates the preferences based on user scores from previous runs.

The tool is **run-agnostic** — it has no internal scheduler, no concept of "daily". It simply executes one full cycle per invocation. Scheduling is handled externally (e.g. crontab on a Raspberry Pi).

---

## Project Structure

```
arxiv-personal-digest/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env                        # API keys (not committed)
├── .env.example
├── seen_papers.json            # Tracks already-processed arXiv IDs
├── preferences.yaml            # User interest profile (LLM-updated)
│
└── src/
    ├── main.py                 # Entry point — orchestrates one full run
    ├── fetcher.py              # Fetch + dedup layer (wraps arxiv.py)
    ├── arxiv.py                # Low-level arXiv API client (fully implemented)
    ├── filter.py               # Uses Claude to filter relevant papers
    ├── notion_utils.py         # Pushes papers to Notion database
    ├── updater.py              # Reads scores from Notion, updates preferences
    ├── models.py               # Pydantic models shared across modules
    └── one-time-runners/
        └── configure_notion_database.py  # One-time Notion DB schema setup
```

---

## How One Run Works

```
main.py
  │
  ├── 1. updater.py     → Read engaged, unprocessed papers from Notion
  │                     → Use Claude to update preferences.yaml
  │                     → Mark consumed papers as Processed=True
  │
  ├── 2. fetcher.py     → Fetch latest abstracts from arXiv
  │                     → Filter out IDs already in seen_papers.json
  │
  ├── 3. filter.py      → Send abstracts + preferences.yaml to Claude
  │                     → Returns: relevant papers + 1 wildcard (exploration)
  │
  └── 4. notion_utils   → Push filtered papers to Notion database
                        → Mark wildcard paper with Explore tag
                        → Append new IDs to seen_papers.json
```

---

## Key Design Decisions

### Run-agnostic
The tool does not know or care how often it runs. It always:
- Looks back at Notion for any unprocessed scores since last run
- Fetches the latest arXiv papers not yet in `seen_papers.json`
- Pushes results to Notion regardless of how much time has passed

### seen_papers.json
Flat list of arXiv paper IDs already processed. Prevents duplicates regardless of run frequency. Committed to Git so it survives reboots.

```json
["2401.12345", "2401.12346", ...]
```

### preferences.yaml
The user's interest profile. Has three sections:
- `interests` — topics to look for (LLM can update)
- `avoid` — topics to filter out (LLM can update)
- `immutable_interests` — hand-written, never touched by the LLM
- `exploration.adjacent_categories` — arXiv categories for wildcard picks
- `example_papers` — seed examples for cold start calibration

```yaml
field: cs.AI
max_results_per_run: 50        # How many abstracts to fetch from arXiv
max_papers_to_push: 5          # Max relevant papers pushed to Notion per run

immutable_interests:
  - LLM agents with tool use
  - Efficient inference and quantization

interests:
  - RAG and retrieval systems for production use
  - LLM fine-tuning on limited hardware

avoid:
  - Pure benchmark papers with no practical application
  - Vision-only models unrelated to language

exploration:
  enabled: true
  wildcard_count: 1
  adjacent_categories:
    - cs.IR
    - cs.HC
    - stat.ML

scoring_history_summary: ""    # Updated by LLM after each run

example_papers:
  - title: "..."
    reason: "I liked this because..."
```

### Preferences Update Rules
Claude may ONLY:
- Modify items under `interests` and `avoid`
- Append new items based on high-scoring wildcards
- Rewrite `scoring_history_summary`

Claude must NEVER:
- Touch `immutable_interests`
- Change `field`, `max_results_per_run`, `max_papers_to_push`
- Remove `example_papers`

### Wildcard / Exploration
Every run, 1 paper from `exploration.adjacent_categories` is injected into the Notion push, tagged as `🔍 Explore`. Wildcard scores are tracked separately in the preferences update step to avoid polluting the main interest signal.

---

## Notion Database Schema

| Column | Type | Description |
|---|---|---|
| `Title` | Title | Paper title |
| `Short Summary` | Text | 2-3 sentence plain-English summary (Claude-generated) |
| `URL` | URL | arXiv link |
| `Abstract` | Text | Full abstract |
| `Why Selected` | Text | Why Claude picked it |
| `Score` | Number | User fills this in (1–5) |
| `Skip Reason` | Select | `off-topic`, `low-quality`, `already-knew-this` |
| `Type` | Select | `Regular`, `🔍 Explore` |
| `Run ID` | Text | Timestamp of the run that pushed it |
| `Processed` | Checkbox | Set by updater after consuming this paper; never set by user |

---

## One-Time Setup

Scripts in `src/one-time-runners/` are run manually once during initial setup. They are not part of the regular run cycle.

| Script | Purpose |
|---|---|
| `configure_notion_database.py` | Patches the Notion database with the required schema (all columns, types, and select options). Run once before the first `main.py` invocation. |
| `first_push.py` | Runs pipeline steps 2–4 (fetch, filter, push) without the updater. Use on the very first run when there are no scored papers in Notion yet. |

Usage:
```bash
python src/one-time-runners/configure_notion_database.py
```

---

## Environment Variables (.env)

```
ANTHROPIC_API_KEY=
NOTION_API_KEY=
NOTION_DATABASE_ID=
```

---

## Dependencies (requirements.txt)

```
anthropic
httpx
notion-client
pydantic
pyyaml
python-dotenv
```

---

## Models (models.py)

```python
class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    url: str

class FilteredPaper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    url: str
    reason: str           # Why Claude selected it (→ "Why Selected" in Notion)
    short_summary: str    # 2-3 sentence plain-English summary (→ "Short Summary" in Notion)
    is_wildcard: bool

class PreferencesUpdate(BaseModel):
    updated_interests: list[str]
    updated_avoid: list[str]
    updated_summary: str
    wildcard_promoted: list[str]   # Topics from wildcards worth adding
```

---

## Error Handling Guidelines

- If arXiv is unreachable: log and exit cleanly, do not update seen_papers.json
- If Claude returns malformed JSON: retry once, then skip the run and alert via log
- If Notion push fails mid-batch: log which IDs succeeded, do not add failed ones to seen_papers.json
- If preferences update fails: log and continue — never block the push step

---

## Crontab Setup (Raspberry Pi)

Scheduling is fully external. Example entries:

```bash
# Once a day at 7am
0 7 * * * /path/to/venv/bin/python /path/to/arxiv-personal-digest/src/main.py >> /var/log/arxiv-digest.log 2>&1

# Twice a week (Mon + Thu at 8am)
0 8 * * 1,4 /path/to/venv/bin/python /path/to/arxiv-personal-digest/src/main.py >> /var/log/arxiv-digest.log 2>&1
```

---

## Paper Engagement & Processing

### What "engaged" means
A paper is considered engaged if the user has either:
- Filled in a **Score** (1–5), or
- Set **Skip Reason** to `off-topic`, `low-quality`, or `already-knew-this`

### The `Processed` flag
After the updater consumes an engaged paper, it calls `mark_papers_processed()` to set `Processed=True` on that page. This prevents the same paper from being re-consumed on the next run.

- `Processed` is set **only by the updater**, never by the user.
- Hide this column from the Notion view via the Properties toggle.

### Deferred scoring scenario
If a paper was pushed weeks ago and the user scores it later, it will still be picked up on the next run as long as `Processed=False`. The updater is time-agnostic — it consumes all engaged+unprocessed papers regardless of when they were pushed.

---

## Development Notes

- Python 3.11+
- Use a virtualenv: `python -m venv venv`
- Test a single run with: `python src/main.py`
- To reset state: clear `seen_papers.json` and manually reset Notion scores
- Keep `preferences.yaml` in Git — its evolution over time is valuable signal

---

## Dependency Notes

### notion-client pinned to 2.3.0

`notion-client==3.0.0` is broken for this project:
- It removed `client.databases.query()` entirely
- It sends `Notion-Version: 2025-09-03` which Notion's API rejects with `400 Invalid request URL`

Pin to `notion-client==2.3.0` which:
- Retains `client.databases.query(database_id=..., start_cursor=...)`
- Uses `Notion-Version: 2022-06-28` which Notion's API accepts

