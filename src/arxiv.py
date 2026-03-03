import logging
import xml.etree.ElementTree as ET

import httpx

from models import Paper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def fetch_papers(field: str, max_results: int) -> list[Paper]:
    """Fetch recent papers from arXiv for a given category.

    Args:
        field: arXiv category (e.g. "cs.AI").
        max_results: Maximum number of papers to fetch.

    Returns:
        List of Paper objects.

    Raises:
        httpx.HTTPStatusError: If arXiv returns a non-200 response.
        httpx.ConnectError: If arXiv is unreachable.
    """
    response = httpx.get(
        ARXIV_API_URL,
        params={
            "search_query": f"cat:{field}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        },
        timeout=30,
    )
    response.raise_for_status()

    root = ET.fromstring(response.text)
    papers = []

    for entry in root.findall(f"{ATOM_NS}entry"):
        try:
            raw_id = entry.findtext(f"{ATOM_NS}id", "")
            arxiv_id = raw_id.rsplit("/", 1)[-1]
            # Strip version suffix (e.g. "2401.12345v1" -> "2401.12345")
            if "v" in arxiv_id:
                arxiv_id = arxiv_id.rsplit("v", 1)[0]

            title = " ".join(entry.findtext(f"{ATOM_NS}title", "").split())
            abstract = " ".join(entry.findtext(f"{ATOM_NS}summary", "").split())
            url = raw_id.strip()

            papers.append(Paper(
                arxiv_id=arxiv_id,
                title=title,
                abstract=abstract,
                url=url,
            ))
        except Exception:
            logger.warning("Failed to parse entry, skipping", exc_info=True)

    return papers
