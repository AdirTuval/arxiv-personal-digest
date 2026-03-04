import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

import fetcher
import filter
import notion_client
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
        4. Push filtered papers to Notion and update seen_papers (notion_client)
    """
    raise NotImplementedError


if __name__ == "__main__":
    load_dotenv(ROOT_DIR / ".env")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()
