import logging
import os

from notion_client import Client

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
    client = Client(auth=os.environ["NOTION_API_KEY"])
    database_id = os.environ["NOTION_DATABASE_ID"]
    pushed_ids = []
    for paper in papers:
        try:
            client.pages.create(
                parent={"database_id": database_id},
                properties={
                    "Title": {"title": [{"text": {"content": paper.title}}]},
                    "URL": {"url": paper.url},
                    "Abstract": {"rich_text": [{"text": {"content": paper.abstract}}]},
                    "Reason": {"rich_text": [{"text": {"content": paper.reason}}]},
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
        List of dicts with keys: arxiv_id, title, score, skip_reason,
        paper_type, scored.
    """
    client = Client(auth=os.environ["NOTION_API_KEY"], notion_version="2022-06-28")
    database_id = os.environ["NOTION_DATABASE_ID"]
    results = []
    cursor = None
    while True:
        body = {}
        if cursor:
            body["start_cursor"] = cursor
        response = client.request(
            path=f"databases/{database_id}/query",
            method="POST",
            body=body,
        )
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
            scored = props.get("Scored", {}).get("checkbox", False)
            results.append({
                "arxiv_id": arxiv_id,
                "title": title,
                "score": score,
                "skip_reason": skip_reason,
                "paper_type": paper_type,
                "scored": scored,
            })
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return results


def fetch_scored_papers() -> list[dict]:
    """Fetch papers from Notion where Scored=True.

    Returns:
        List of dicts with keys: arxiv_id, title, score, skip_reason,
        paper_type, scored.
    """
    return [p for p in fetch_papers() if p.get("scored")]
