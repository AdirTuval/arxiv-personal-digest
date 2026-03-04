import logging
import os

from notion_client import Client

from models import FilteredPaper

logger = logging.getLogger(__name__)

ACTIVE_SKIP_REASONS = {"off-topic", "low-quality", "already-knew-this"}


def push_papers(papers: list[FilteredPaper], run_id: str) -> list[str]:
    """Create Notion pages for each filtered paper.

    Args:
        papers: Papers to push, including wildcard papers tagged with
                is_wildcard=True (shown as '🔍 Explore' type in Notion).
        run_id: Timestamp identifier for this run.

    Returns:
        List of arxiv_ids that were successfully pushed.
    """
    client = Client(auth=os.environ["NOTION_API_KEY"])
    database_id = os.environ["NOTION_DATABASE_ID"]
    pushed_ids = []
    for paper in papers:
        try:
            client.pages.create(
                parent={"database_id": database_id},
                properties={
                    "Title": {"title": [{"text": {"content": paper.title}}]},
                    "Short Summary": {"rich_text": [{"text": {"content": paper.short_summary}}]},
                    "URL": {"url": paper.url},
                    "Abstract": {"rich_text": [{"text": {"content": paper.abstract}}]},
                    "Why Selected": {"rich_text": [{"text": {"content": paper.reason}}]},
                    "Type": {"select": {"name": "🔍 Explore" if paper.is_wildcard else "Regular"}},
                    "Run ID": {"rich_text": [{"text": {"content": run_id}}]},
                },
            )
            pushed_ids.append(paper.arxiv_id)
        except Exception:
            logger.exception("Failed to push paper %s", paper.arxiv_id)
    return pushed_ids


def fetch_papers() -> list[dict]:
    """Fetch all papers from the Notion database.

    Returns:
        List of dicts with keys: page_id, arxiv_id, title, score,
        skip_reason, paper_type, processed.
    """
    client = Client(auth=os.environ["NOTION_API_KEY"])
    database_id = os.environ["NOTION_DATABASE_ID"]
    results = []
    cursor = None
    while True:
        kwargs = {"database_id": database_id}
        if cursor:
            kwargs["start_cursor"] = cursor
        response = client.databases.query(**kwargs)
        for page in response["results"]:
            props = page["properties"]
            title_list = props.get("Title", {}).get("title", [])
            title = title_list[0]["plain_text"] if title_list else ""
            url = props.get("URL", {}).get("url") or ""
            arxiv_id = url.rstrip("/").split("/")[-1] if url else ""
            score = props.get("Score", {}).get("number")
            skip_reason_sel = props.get("Skip Reason", {}).get("select")
            skip_reason = skip_reason_sel["name"] if skip_reason_sel else None
            type_sel = props.get("Type", {}).get("select")
            paper_type = type_sel["name"] if type_sel else "Regular"
            processed = props.get("Processed", {}).get("checkbox", False)
            results.append({
                "page_id": page["id"],
                "arxiv_id": arxiv_id,
                "title": title,
                "score": score,
                "skip_reason": skip_reason,
                "paper_type": paper_type,
                "processed": processed,
            })
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return results


def _is_engaged(paper: dict) -> bool:
    return (
        paper.get("score") is not None
        or paper.get("skip_reason") in ACTIVE_SKIP_REASONS
    ) and not paper.get("processed", False)


def fetch_scored_papers() -> list[dict]:
    """Fetch papers from Notion that the user has engaged with (scored or
    actively skipped) and have not yet been processed by the updater.

    Returns:
        List of dicts with keys: page_id, arxiv_id, title, score,
        skip_reason, paper_type, processed.
    """
    return [p for p in fetch_papers() if _is_engaged(p)]


def mark_papers_processed(page_ids: list[str]) -> None:
    """Set Processed=True on each Notion page so the updater won't re-consume them.

    Args:
        page_ids: Notion page IDs to mark as processed.
    """
    client = Client(auth=os.environ["NOTION_API_KEY"])
    for page_id in page_ids:
        try:
            client.pages.update(
                page_id=page_id,
                properties={"Processed": {"checkbox": True}},
            )
        except Exception:
            logger.exception("Failed to mark page %s as processed", page_id)
