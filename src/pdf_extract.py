import logging

import httpx
import pymupdf

logger = logging.getLogger(__name__)

PDF_URL_TEMPLATE = "https://arxiv.org/pdf/{arxiv_id}.pdf"
DOWNLOAD_TIMEOUT = 60


def download_pdf(arxiv_id: str, timeout: int = DOWNLOAD_TIMEOUT) -> bytes:
    """Download a PDF from arXiv.

    Args:
        arxiv_id: The arXiv paper ID (e.g. "2401.12345").
        timeout: Request timeout in seconds.

    Returns:
        Raw PDF bytes.
    """
    url = PDF_URL_TEMPLATE.format(arxiv_id=arxiv_id)
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.content


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract plain text from PDF bytes using pymupdf.

    Args:
        pdf_bytes: Raw PDF file content.

    Returns:
        Extracted text as a single string.
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text_parts = []
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def fetch_paper_full_text(arxiv_id: str) -> str:
    """Download and extract text from an arXiv paper PDF.

    Returns empty string on any failure (logged, never raises).
    """
    try:
        pdf_bytes = download_pdf(arxiv_id)
        return extract_text_from_pdf(pdf_bytes)
    except Exception:
        logger.exception("Failed to fetch full text for %s", arxiv_id)
        return ""


def fetch_paper_full_texts(arxiv_ids: list[str]) -> dict[str, str]:
    """Batch fetch full texts for multiple papers.

    Args:
        arxiv_ids: List of arXiv IDs.

    Returns:
        Dict mapping arxiv_id to extracted text (empty string on failure).
    """
    results = {}
    for arxiv_id in arxiv_ids:
        results[arxiv_id] = fetch_paper_full_text(arxiv_id)
    return results
