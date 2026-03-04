import logging

from models import FilteredPaper

logger = logging.getLogger(__name__)


def push_papers(papers: list[FilteredPaper], run_id: str) -> list[str]:
    """Create Notion pages for each filtered paper.

    Args:
        papers: Papers to push, including wildcard papers tagged with
                is_wildcard=True (shown as '🔍 Explore' type in Notion).
        run_id: Timestamp identifier for this run.

    Returns:
        List of arxiv_ids that were successfully pushed.
    """
    raise NotImplementedError


def fetch_scored_papers() -> list[dict]:
    """Fetch papers from Notion where Scored=True and not yet processed.

    Returns:
        List of dicts with keys: arxiv_id, title, score, skip_reason,
        paper_type ('Regular' or '🔍 Explore').
    """
    raise NotImplementedError
