from unittest.mock import MagicMock, call, patch

import pytest

from models import FilteredPaper
from notion_utils import fetch_scored_papers, push_papers


def _make_filtered_paper(arxiv_id, is_wildcard=False):
    return FilteredPaper(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        abstract=f"Abstract for {arxiv_id}",
        url=f"http://arxiv.org/abs/{arxiv_id}",
        reason="Selected for relevance",
        is_wildcard=is_wildcard,
    )


class TestPushPapers:
    @patch("notion_utils.Client", create=True)
    def test_push_papers_creates_pages(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        papers = [
            _make_filtered_paper("2401.12345"),
            _make_filtered_paper("2401.12346"),
        ]

        result = push_papers(papers, run_id="2024-01-15T07:00:00Z")

        assert len(result) == 2
        assert "2401.12345" in result
        assert "2401.12346" in result
        assert mock_client.pages.create.call_count == 2

    @patch("notion_utils.Client", create=True)
    def test_push_papers_sets_explore_type_for_wildcard(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        papers = [_make_filtered_paper("2401.12345", is_wildcard=True)]

        push_papers(papers, run_id="2024-01-15T07:00:00Z")

        create_call = mock_client.pages.create.call_args
        properties = create_call.kwargs.get("properties") or create_call[1].get(
            "properties"
        )
        type_val = properties.get("Type", {}).get("select", {}).get("name", "")
        assert type_val == "\ud83d\udd0d Explore"

    @patch("notion_utils.Client", create=True)
    def test_push_papers_sets_regular_type(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        papers = [_make_filtered_paper("2401.12345", is_wildcard=False)]

        push_papers(papers, run_id="2024-01-15T07:00:00Z")

        create_call = mock_client.pages.create.call_args
        properties = create_call.kwargs.get("properties") or create_call[1].get(
            "properties"
        )
        type_val = properties.get("Type", {}).get("select", {}).get("name", "")
        assert type_val == "Regular"

    @patch("notion_utils.Client", create=True)
    def test_push_papers_includes_run_id(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        papers = [_make_filtered_paper("2401.12345")]
        run_id = "2024-01-15T07:00:00Z"

        push_papers(papers, run_id=run_id)

        create_call = mock_client.pages.create.call_args
        properties = create_call.kwargs.get("properties") or create_call[1].get(
            "properties"
        )
        run_id_val = (
            properties.get("Run ID", {})
            .get("rich_text", [{}])[0]
            .get("text", {})
            .get("content", "")
        )
        assert run_id_val == run_id

    @patch("notion_utils.Client", create=True)
    def test_push_papers_empty_list(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client

        result = push_papers([], run_id="2024-01-15T07:00:00Z")

        assert result == []
        mock_client.pages.create.assert_not_called()

    @patch("notion_utils.Client", create=True)
    def test_push_papers_partial_failure(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        # First call succeeds, second raises
        mock_client.pages.create.side_effect = [
            {"id": "page-1"},
            Exception("Notion API error"),
        ]

        papers = [
            _make_filtered_paper("2401.12345"),
            _make_filtered_paper("2401.12346"),
        ]

        result = push_papers(papers, run_id="2024-01-15T07:00:00Z")

        assert "2401.12345" in result
        assert "2401.12346" not in result


class TestFetchScoredPapers:
    @patch("notion_utils.Client", create=True)
    def test_fetch_scored_papers_returns_dicts(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.databases.query.return_value = {
            "results": [
                {
                    "properties": {
                        "Title": {"title": [{"plain_text": "Paper A"}]},
                        "URL": {"url": "http://arxiv.org/abs/2401.12345"},
                        "Score": {"number": 4},
                        "Skip Reason": {"select": None},
                        "Type": {"select": {"name": "Regular"}},
                        "Scored": {"checkbox": True},
                    }
                }
            ],
            "has_more": False,
        }

        result = fetch_scored_papers()

        assert isinstance(result, list)
        assert len(result) == 1
        paper = result[0]
        assert "arxiv_id" in paper
        assert "title" in paper
        assert "score" in paper
        assert "skip_reason" in paper
        assert "paper_type" in paper

    @patch("notion_utils.Client", create=True)
    def test_fetch_scored_papers_filters_scored_only(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        # The implementation should query with a filter for Scored=True
        mock_client.databases.query.return_value = {
            "results": [
                {
                    "properties": {
                        "Title": {"title": [{"plain_text": "Scored Paper"}]},
                        "URL": {"url": "http://arxiv.org/abs/2401.12345"},
                        "Score": {"number": 5},
                        "Skip Reason": {"select": None},
                        "Type": {"select": {"name": "Regular"}},
                        "Scored": {"checkbox": True},
                    }
                }
            ],
            "has_more": False,
        }

        result = fetch_scored_papers()

        # Verify the query included a filter for Scored checkbox
        query_call = mock_client.databases.query.call_args
        query_filter = query_call.kwargs.get("filter") or query_call[1].get("filter", {})
        # The filter should reference the Scored checkbox
        filter_str = str(query_filter)
        assert "Scored" in filter_str or "scored" in filter_str.lower()

    @patch("notion_utils.Client", create=True)
    def test_fetch_scored_papers_empty_database(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.databases.query.return_value = {
            "results": [],
            "has_more": False,
        }

        result = fetch_scored_papers()

        assert result == []
