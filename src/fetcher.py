import json
import logging
from pathlib import Path

from models import Paper
from arxiv import fetch_papers

logger = logging.getLogger(__name__)

DEFAULT_SEEN_PATH = Path(__file__).resolve().parent.parent / "seen_papers.json"


def load_seen_papers(path: Path = DEFAULT_SEEN_PATH) -> set[str]:
    """Load the set of already-processed arXiv IDs from disk."""
    if not path.exists():
        return set()
    return set(json.loads(path.read_text()))


def save_seen_papers(path: Path, seen: set[str]) -> None:
    """Persist the set of seen arXiv IDs to disk."""
    path.write_text(json.dumps(sorted(seen)))


def fetch_new_papers(
    field: str,
    max_results: int,
    seen_papers_path: Path = DEFAULT_SEEN_PATH,
) -> list[Paper]:
    """Fetch papers from arXiv and filter out already-seen IDs.

    Uses arxiv.fetch_papers() internally, then removes any paper whose
    arxiv_id is already in the seen-papers file.
    """
    seen = load_seen_papers(seen_papers_path)
    papers = fetch_papers(field, max_results)
    return [p for p in papers if p.arxiv_id not in seen]
