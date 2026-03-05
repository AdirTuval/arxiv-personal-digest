# arxiv-personal-digest

A self-improving arXiv paper curation tool that learns your research taste over time. Powered by Claude AI, integrated with Notion, and designed to run headlessly on a Raspberry Pi via cron.

## How It Works

The tool runs a closed-loop cycle: it fetches papers, filters them with an LLM, pushes picks to Notion for you to score, then refines its understanding of your interests based on those scores.

```
┌─────────────────────────────────────────────────────────┐
│                    One Run Cycle                        │
│                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐   │
│  │  arXiv   │───▶│  Claude  │───▶│  Notion Database │   │
│  │  (fetch) │    │ (filter) │    │  (push papers)   │   │
│  └──────────┘    └──────────┘    └────────┬─────────┘   │
│                                           │             │
│                                     User scores         │
│                                     papers (1-5)        │
│                                           │             │
│  ┌──────────────────┐    ┌────────────────▼─────────┐   │
│  │  preferences.yaml│◀───│  Claude (update prefs)   │   │
│  │  (refined)       │    │  + PDF full-text reading  │   │
│  └──────────────────┘    └──────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

The tool is **run-agnostic** — it has no internal scheduler and no concept of "daily." It executes one full cycle per invocation. Scheduling is handled externally (e.g., crontab).

## Architecture

```
src/
├── main.py            Orchestrator — runs the 4-step pipeline
├── arxiv.py           Low-level arXiv API client (httpx, XML parsing)
├── fetcher.py         Dedup layer over arxiv.py using seen_papers.json
├── filter.py          Delegates to llm.py for paper selection
├── llm.py             All Claude API calls (filter + preference update)
├── notion_utils.py    Notion CRUD (push papers, fetch scores, mark processed)
├── updater.py         Reads scores, fetches PDFs, calls Claude to update preferences
├── pdf_extract.py     Downloads arXiv PDFs, extracts text via PyMuPDF
├── models.py          Pydantic data models (Paper, FilteredPaper, PreferencesUpdate)
└── one-time-runners/
    └── configure_notion_database.py   One-time Notion DB schema setup
```

## The Pipeline

Each invocation of `main.py` runs four steps in order:

### 1. Update Preferences

Fetch all engaged, unprocessed papers from Notion. Download their PDFs and extract full text. Send the scored papers (with full text for up to 8 papers) and current preferences to Claude, which refines the `interests` and `avoid` lists and rewrites the `scoring_history_summary`. A timestamped snapshot of the previous preferences is saved to `historical_preferences/` before any changes. Finally, consumed papers are marked `Processed=True` in Notion.

### 2. Fetch Papers

Query the arXiv API for the latest papers in the configured field (e.g., `cs.AI`). Deduplicate against `seen_papers.json` to avoid processing any paper twice.

### 3. Filter Papers

Send all new abstracts along with the full `preferences.yaml` to Claude. Claude selects up to `max_papers_to_push` relevant papers, each with a plain-English summary and a reason for selection. If exploration is enabled, Claude also picks 1 wildcard paper from adjacent categories.

### 4. Push to Notion

Create a Notion page for each filtered paper with title, short summary, abstract, selection reason, and type tag. Update `seen_papers.json` with all successfully pushed paper IDs.

## Notion Integration

### Database Schema

| Column | Type | Description |
|---|---|---|
| Title | Title | Paper title |
| Short Summary | Text | 2-3 sentence plain-English summary |
| URL | URL | arXiv link |
| Abstract | Text | Full abstract |
| Why Selected | Text | Why Claude picked this paper |
| Score | Number | User fills in (1-5) |
| Skip Reason | Select | `off-topic`, `low-quality`, `already-knew-this` |
| Type | Select | `Regular` or `🔍 Explore` |
| Run ID | Text | Timestamp of the run that pushed it |
| Processed | Checkbox | Set by the updater after consuming the paper |

### User Workflow

Papers appear in your Notion database after each run. Review them and either assign a **Score** (1-5) or select a **Skip Reason**. On the next run, the updater consumes these signals and refines your preferences.

### Engagement Model

A paper is considered "engaged" if the user has either:
- Filled in a **Score** (1-5), or
- Set a **Skip Reason** of `off-topic`, `low-quality`, or `already-knew-this`

### The Processed Flag

After the updater consumes a paper's score, it sets `Processed=True` to prevent re-consumption. This flag is managed entirely by the system — hide it from your Notion view. Papers scored weeks later are still picked up on the next run as long as `Processed=False`.

### One-Time Setup

Run the schema setup script once before the first pipeline invocation:

```bash
python src/one-time-runners/configure_notion_database.py
```

## Preferences System

The file `preferences.yaml` is the user's evolving interest profile:

```yaml
field: cs.AI                        # arXiv category to query
max_results_per_run: 50             # Abstracts fetched per run
max_papers_to_push: 5               # Max papers pushed to Notion per run

immutable_interests:                # Hand-written, never modified by Claude
  - LLM agents with tool use
  - Efficient inference and quantization

interests:                          # Claude can add, refine, or remove
  - RAG and retrieval systems for production use
  - LLM fine-tuning on limited hardware

avoid:                              # Claude can add, refine, or remove
  - Pure benchmark papers with no practical application
  - Vision-only models unrelated to language

exploration:
  enabled: true
  wildcard_count: 1
  adjacent_categories:              # Categories for wildcard picks
    - cs.IR
    - cs.HC
    - stat.ML

scoring_history_summary: ""         # Claude's running analysis of scoring patterns

example_papers:                     # Seed examples for cold-start calibration
  - title: "ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs"
    reason: "Practical tool-use framework with real API integration"
```

### What Claude Can Modify

| Field | Mutable? |
|---|---|
| `interests` | Yes — add, refine, remove based on scores |
| `avoid` | Yes — add, refine, remove based on skip reasons |
| `scoring_history_summary` | Yes — rewritten each update cycle |
| `immutable_interests` | No |
| `field`, `max_results_per_run`, `max_papers_to_push` | No |
| `example_papers` | No |
| `exploration` | No |

### Historical Snapshots

Before each preference update, the current `preferences.yaml` is copied to `historical_preferences/preferences_YYYYMMDD_HHMMSS.yaml`. This provides a full audit trail of how your interests evolve over time.

## Wildcard / Exploration

Each run includes 1 paper from `exploration.adjacent_categories` (e.g., `cs.IR`, `cs.HC`, `stat.ML`), tagged as `🔍 Explore` in Notion. This prevents filter bubbles by surfacing serendipitous finds outside your main field.

When a wildcard paper scores 4+, Claude promotes its topic into the regular `interests` list — the system naturally broadens its scope based on what you actually find valuable.

## Tech Stack

- **Python 3.11+**
- **Claude API** (Anthropic) — `claude-sonnet-4-20250514` for filtering and preference updates
- **arXiv API** — Atom XML feed, no authentication required
- **Notion API** — via `notion-client==2.3.0` (pinned; v3 breaks compatibility)
- **PyMuPDF** — PDF text extraction for richer preference learning
- **httpx** — HTTP client for arXiv and PDF downloads
- **Pydantic** — data validation for pipeline models
- **PyYAML** — preferences file parsing
- **python-dotenv** — environment variable management

## Setup & Installation

```bash
# Clone
git clone https://github.com/AdirTuval/arxiv-personal-digest.git
cd arxiv-personal-digest

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file with your API keys:

```
ANTHROPIC_API_KEY=sk-ant-...
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=your-database-id
```

Run the one-time Notion database setup:

```bash
python src/one-time-runners/configure_notion_database.py
```

Edit `preferences.yaml` with your initial interests, then run:

```bash
python src/main.py
```

## Scheduling (Crontab)

The tool is designed to run headlessly on a Raspberry Pi. Example crontab entries:

```bash
# Once a day at 7am
0 7 * * * /path/to/venv/bin/python /path/to/arxiv-personal-digest/src/main.py >> /var/log/arxiv-digest.log 2>&1

# Twice a week (Mon + Thu at 8am)
0 8 * * 1,4 /path/to/venv/bin/python /path/to/arxiv-personal-digest/src/main.py >> /var/log/arxiv-digest.log 2>&1
```

## Error Handling

The pipeline is designed for resilience:

- **Updater failures** don't block the rest of the pipeline — fetch, filter, and push still run
- **PDF download/extraction failures** degrade gracefully (empty text, logged)
- **Notion push failures** are per-paper — successfully pushed papers are still recorded in `seen_papers.json`
- **JSON parse errors** from Claude trigger one automatic retry with a corrective prompt

## Development

```bash
# Run tests
pytest

# Run a single cycle
python src/main.py

# Reset state (start fresh)
# Clear seen_papers.json and manually reset Notion scores
```

### Dependency Note

`notion-client` is pinned to `2.3.0`. Version 3.0.0 removed `client.databases.query()` and sends a `Notion-Version` header that Notion's API rejects with `400 Invalid request URL`. Do not upgrade.
