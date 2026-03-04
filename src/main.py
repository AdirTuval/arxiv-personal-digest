import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

import fetcher
import filter
import notion_utils
import updater

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent.parent
PREFERENCES_PATH = ROOT_DIR / "preferences.yaml"
SEEN_PAPERS_PATH = ROOT_DIR / "seen_papers.json"


def run() -> None:
    """Execute one full digest cycle.

    Steps:
        1. Update preferences from scored Notion papers (updater)
        2. Fetch new papers from arXiv, deduping via seen_papers (fetcher)
        3. Filter papers using Claude + preferences (filter)
        4. Push filtered papers to Notion and update seen_papers (notion_utils)
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logger.info("Starting run %s", run_id)

    # Step 1: Update preferences from scored papers
    try:
        scored_papers = notion_utils.fetch_scored_papers()
        updater.update_preferences(scored_papers, PREFERENCES_PATH)
        if scored_papers:
            page_ids = [p["page_id"] for p in scored_papers]
            notion_utils.mark_papers_processed(page_ids)
            logger.info("Processed %d scored papers", len(scored_papers))
    except Exception:
        logger.exception("Updater failed, continuing with rest of pipeline")

    # Step 2: Fetch new papers
    preferences = yaml.safe_load(Path.read_text(PREFERENCES_PATH))
    field = preferences["field"]
    max_results = preferences["max_results_per_run"]

    new_papers = fetcher.fetch_new_papers(field, max_results, SEEN_PAPERS_PATH)
    logger.info("Fetched %d new papers", len(new_papers))

    if not new_papers:
        logger.info("No new papers, skipping filter and push")
        return

    # Step 3: Filter papers
    filtered = filter.filter_papers(new_papers, preferences)
    logger.info("Filtered to %d papers", len(filtered))

    if not filtered:
        logger.info("No papers passed filter")
        return

    # Step 4: Push to Notion and update seen papers
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
