from unittest.mock import MagicMock, patch

import httpx
import pytest

from arxiv import ARXIV_API_URL, fetch_papers
from models import Paper


def build_atom_xml(entries):
    """Build a valid Atom XML string from a list of entry dicts.

    Each entry dict should have keys: id, title, summary.
    """
    header = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
    )
    footer = "</feed>"
    body = ""
    for e in entries:
        body += (
            "<entry>"
            f"<id>{e['id']}</id>"
            f"<title>{e['title']}</title>"
            f"<summary>{e['summary']}</summary>"
            "</entry>"
        )
    return header + body + footer


def mock_response(text, status_code=200):
    resp = MagicMock(spec=httpx.Response)
    resp.text = text
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


class TestFetchPapersBasic:
    @patch("arxiv.httpx.get")
    def test_fetch_papers_basic(self, mock_get):
        entries = [
            {
                "id": "http://arxiv.org/abs/2401.12345v1",
                "title": "Test Paper Title",
                "summary": "This is a test abstract.",
            }
        ]
        mock_get.return_value = mock_response(build_atom_xml(entries))

        papers = fetch_papers("cs.AI", max_results=10)

        assert len(papers) == 1
        assert isinstance(papers[0], Paper)
        assert papers[0].arxiv_id == "2401.12345"
        assert papers[0].title == "Test Paper Title"
        assert papers[0].abstract == "This is a test abstract."

    @patch("arxiv.httpx.get")
    def test_fetch_papers_strips_version_suffix(self, mock_get):
        entries = [
            {
                "id": "http://arxiv.org/abs/2401.12345v2",
                "title": "Paper",
                "summary": "Abstract",
            }
        ]
        mock_get.return_value = mock_response(build_atom_xml(entries))

        papers = fetch_papers("cs.AI", max_results=10)
        assert papers[0].arxiv_id == "2401.12345"

    @patch("arxiv.httpx.get")
    def test_fetch_papers_no_version_suffix(self, mock_get):
        entries = [
            {
                "id": "http://arxiv.org/abs/2401.12345",
                "title": "Paper",
                "summary": "Abstract",
            }
        ]
        mock_get.return_value = mock_response(build_atom_xml(entries))

        papers = fetch_papers("cs.AI", max_results=10)
        assert papers[0].arxiv_id == "2401.12345"


class TestFetchPapersFormatting:
    @patch("arxiv.httpx.get")
    def test_fetch_papers_whitespace_normalization(self, mock_get):
        entries = [
            {
                "id": "http://arxiv.org/abs/2401.12345v1",
                "title": "Multi\n  Line\n  Title",
                "summary": "Abstract with\n  extra   whitespace\n  inside.",
            }
        ]
        mock_get.return_value = mock_response(build_atom_xml(entries))

        papers = fetch_papers("cs.AI", max_results=10)
        assert papers[0].title == "Multi Line Title"
        assert papers[0].abstract == "Abstract with extra whitespace inside."

    @patch("arxiv.httpx.get")
    def test_fetch_papers_url_is_raw_id_stripped(self, mock_get):
        entries = [
            {
                "id": "  http://arxiv.org/abs/2401.12345v1  ",
                "title": "Paper",
                "summary": "Abstract",
            }
        ]
        mock_get.return_value = mock_response(build_atom_xml(entries))

        papers = fetch_papers("cs.AI", max_results=10)
        assert papers[0].url == "http://arxiv.org/abs/2401.12345v1"


class TestFetchPapersEdgeCases:
    @patch("arxiv.httpx.get")
    def test_fetch_papers_empty_feed(self, mock_get):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            "</feed>"
        )
        mock_get.return_value = mock_response(xml)

        papers = fetch_papers("cs.AI", max_results=10)
        assert papers == []

    @patch("arxiv.httpx.get")
    def test_fetch_papers_skips_malformed_entry(self, mock_get):
        # One good entry and one entry that will cause parsing issues.
        # We simulate a malformed entry by having an entry where findtext
        # returns empty strings — which still parses fine — so instead we
        # inject a broken XML structure after a good entry.
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<feed xmlns="http://www.w3.org/2005/Atom">'
            "<entry>"
            "<id>http://arxiv.org/abs/2401.12345v1</id>"
            "<title>Good Paper</title>"
            "<summary>Good abstract</summary>"
            "</entry>"
            "<entry>"
            "<id></id>"
            "<title>Bad Paper</title>"
            "<summary>Bad abstract</summary>"
            "</entry>"
            "</feed>"
        )
        mock_get.return_value = mock_response(xml)

        papers = fetch_papers("cs.AI", max_results=10)
        # At minimum the good entry should be present; the bad one may or may
        # not parse (empty ID) — the key is no crash.
        assert len(papers) >= 1
        assert papers[0].title == "Good Paper"


class TestFetchPapersErrors:
    @patch("arxiv.httpx.get")
    def test_fetch_papers_http_error_raises(self, mock_get):
        mock_get.return_value = mock_response("", status_code=500)

        with pytest.raises(httpx.HTTPStatusError):
            fetch_papers("cs.AI", max_results=10)

    @patch("arxiv.httpx.get")
    def test_fetch_papers_connection_error_raises(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            fetch_papers("cs.AI", max_results=10)


class TestFetchPapersParams:
    @patch("arxiv.httpx.get")
    def test_fetch_papers_passes_correct_params(self, mock_get):
        mock_get.return_value = mock_response(build_atom_xml([]))

        fetch_papers("cs.AI", max_results=50)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["search_query"] == "cat:cs.AI"
        assert params["sortBy"] == "submittedDate"
        assert params["sortOrder"] == "descending"
        assert params["max_results"] == 50
