"""First-push bootstrap runner.

Runs steps 2-4 of the main pipeline (fetch, filter, push) without the updater.
Use this on the very first run when there are no scored papers in Notion yet.
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fetcher
import filter
import notion_utils

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PREFERENCES_PATH = ROOT_DIR / "preferences.yaml"
SEEN_PAPERS_PATH = ROOT_DIR / "seen_papers.json"


def run() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info("Starting first-push run %s", run_id)

    preferences = yaml.safe_load(PREFERENCES_PATH.read_text())
    field = preferences["field"]
    max_results = preferences["max_results_per_run"]

    new_papers = fetcher.fetch_new_papers(field, max_results, SEEN_PAPERS_PATH)
    logger.info("Fetched %d new papers", len(new_papers))

    if not new_papers:
        logger.info("No new papers, nothing to push")
        return

    filtered = filter.filter_papers(new_papers, preferences)
    logger.info("Filtered to %d papers", len(filtered))

    if not filtered:
        logger.info("No papers passed filter")
        return

    pushed_ids = notion_utils.push_papers(filtered, run_id)
    logger.info("Pushed %d papers to Notion", len(pushed_ids))

    seen = fetcher.load_seen_papers(SEEN_PAPERS_PATH)
    seen.update(pushed_ids)
    fetcher.save_seen_papers(SEEN_PAPERS_PATH, seen)


if __name__ == "__main__":
    load_dotenv(ROOT_DIR / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()
