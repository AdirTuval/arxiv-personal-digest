import os
from unittest.mock import MagicMock, patch

import pytest

from models import FilteredPaper
from notion_utils import fetch_papers, fetch_scored_papers, mark_papers_processed, push_papers

_NOTION_ENV = {"NOTION_API_KEY": "test-key", "NOTION_DATABASE_ID": "test-db-id"}


def _make_filtered_paper(arxiv_id, is_wildcard=False):
    return FilteredPaper(
        arxiv_id=arxiv_id,
        title=f"Paper {arxiv_id}",
        abstract=f"Abstract for {arxiv_id}",
        url=f"http://arxiv.org/abs/{arxiv_id}",
        reason="Selected for relevance",
        short_summary="A brief summary of the paper.",
        is_wildcard=is_wildcard,
    )


def _make_notion_page(arxiv_id, title, processed=False, score=None, skip_reason=None, paper_type="Regular"):
    return {
        "id": f"page-{arxiv_id}",
        "properties": {
            "Title": {"title": [{"plain_text": title}]},
            "URL": {"url": f"http://arxiv.org/abs/{arxiv_id}"},
            "Score": {"number": score},
            "Skip Reason": {"select": {"name": skip_reason} if skip_reason else None},
            "Type": {"select": {"name": paper_type}},
            "Processed": {"checkbox": processed},
            "Short Summary": {"rich_text": [{"plain_text": "A brief summary."}]},
            "Why Selected": {"rich_text": [{"plain_text": "Reason text."}]},
        },
    }


@patch.dict(os.environ, {"NOTION_API_KEY": "test-key", "NOTION_DATABASE_ID": "test-db-id"})
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
        assert type_val == "🔍 Explore"

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
    def test_push_papers_includes_short_summary(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        papers = [_make_filtered_paper("2401.12345")]

        push_papers(papers, run_id="2024-01-15T07:00:00Z")

        create_call = mock_client.pages.create.call_args
        properties = create_call.kwargs.get("properties") or create_call[1].get(
            "properties"
        )
        summary_val = (
            properties.get("Short Summary", {})
            .get("rich_text", [{}])[0]
            .get("text", {})
            .get("content", "")
        )
        assert summary_val == "A brief summary of the paper."

    @patch("notion_utils.Client", create=True)
    def test_push_papers_uses_why_selected_key(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}

        papers = [_make_filtered_paper("2401.12345")]

        push_papers(papers, run_id="2024-01-15T07:00:00Z")

        create_call = mock_client.pages.create.call_args
        properties = create_call.kwargs.get("properties") or create_call[1].get(
            "properties"
        )
        assert "Why Selected" in properties
        assert "Reason" not in properties

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


@patch.dict(os.environ, {"NOTION_API_KEY": "test-key", "NOTION_DATABASE_ID": "test-db-id"})
class TestFetchPapers:
    @patch("notion_utils.Client", create=True)
    def test_fetch_papers_returns_dicts(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.databases.query.return_value = {
            "results": [_make_notion_page("2401.12345", "Paper A", processed=False, score=4)],
            "has_more": False,
        }

        result = fetch_papers()

        assert isinstance(result, list)
        assert len(result) == 1
        paper = result[0]
        assert "page_id" in paper
        assert "arxiv_id" in paper
        assert "title" in paper
        assert "score" in paper
        assert "skip_reason" in paper
        assert "paper_type" in paper
        assert "processed" in paper
        assert "scored" not in paper
        assert paper["arxiv_id"] == "2401.12345"
        assert paper["title"] == "Paper A"
        assert paper["page_id"] == "page-2401.12345"

    @patch("notion_utils.Client", create=True)
    def test_fetch_papers_queries_all(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.databases.query.return_value = {
            "results": [
                _make_notion_page("2401.00001", "Scored Paper", processed=False, score=5),
                _make_notion_page("2401.00002", "Unscored Paper", processed=False),
            ],
            "has_more": False,
        }

        result = fetch_papers()

        assert len(result) == 2
        arxiv_ids = [p["arxiv_id"] for p in result]
        assert "2401.00001" in arxiv_ids
        assert "2401.00002" in arxiv_ids

    @patch("notion_utils.Client", create=True)
    def test_fetch_papers_empty_database(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.databases.query.return_value = {
            "results": [],
            "has_more": False,
        }

        result = fetch_papers()

        assert result == []

    @patch("notion_utils.Client", create=True)
    def test_fetch_papers_handles_pagination(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.databases.query.side_effect = [
            {
                "results": [_make_notion_page("2401.00001", "Page 1 Paper")],
                "has_more": True,
                "next_cursor": "cursor-abc",
            },
            {
                "results": [_make_notion_page("2401.00002", "Page 2 Paper")],
                "has_more": False,
            },
        ]

        result = fetch_papers()

        assert len(result) == 2
        arxiv_ids = [p["arxiv_id"] for p in result]
        assert "2401.00001" in arxiv_ids
        assert "2401.00002" in arxiv_ids
        assert mock_client.databases.query.call_count == 2


class TestFetchScoredPapers:
    @patch("notion_utils.fetch_papers")
    def test_returns_paper_with_score(self, mock_fetch_papers):
        mock_fetch_papers.return_value = [
            {"arxiv_id": "2401.00001", "score": 4, "skip_reason": None, "processed": False},
            {"arxiv_id": "2401.00002", "score": None, "skip_reason": None, "processed": False},
        ]

        result = fetch_scored_papers()

        assert len(result) == 1
        assert result[0]["arxiv_id"] == "2401.00001"

    @patch("notion_utils.fetch_papers")
    def test_returns_paper_with_active_skip_reason(self, mock_fetch_papers):
        mock_fetch_papers.return_value = [
            {"arxiv_id": "2401.00001", "score": None, "skip_reason": "off-topic", "processed": False},
            {"arxiv_id": "2401.00002", "score": None, "skip_reason": "low-quality", "processed": False},
            {"arxiv_id": "2401.00003", "score": None, "skip_reason": "already-knew-this", "processed": False},
        ]

        result = fetch_scored_papers()

        assert len(result) == 3

    @patch("notion_utils.fetch_papers")
    def test_excludes_unknown_skip_reason(self, mock_fetch_papers):
        mock_fetch_papers.return_value = [
            {"arxiv_id": "2401.00001", "score": None, "skip_reason": "unknown-reason", "processed": False},
            {"arxiv_id": "2401.00002", "score": 3, "skip_reason": None, "processed": False},
        ]

        result = fetch_scored_papers()

        assert len(result) == 1
        assert result[0]["arxiv_id"] == "2401.00002"

    @patch("notion_utils.fetch_papers")
    def test_excludes_already_processed(self, mock_fetch_papers):
        mock_fetch_papers.return_value = [
            {"arxiv_id": "2401.00001", "score": 4, "skip_reason": None, "processed": True},
            {"arxiv_id": "2401.00002", "score": 5, "skip_reason": None, "processed": False},
        ]

        result = fetch_scored_papers()

        assert len(result) == 1
        assert result[0]["arxiv_id"] == "2401.00002"

    @patch("notion_utils.fetch_papers")
    def test_empty_when_none_engaged(self, mock_fetch_papers):
        mock_fetch_papers.return_value = [
            {"arxiv_id": "2401.00001", "score": None, "skip_reason": None, "processed": False},
            {"arxiv_id": "2401.00002", "score": None, "skip_reason": None, "processed": False},
        ]

        result = fetch_scored_papers()

        assert result == []

    @patch("notion_utils.fetch_papers")
    def test_score_and_active_skip_both_qualify(self, mock_fetch_papers):
        mock_fetch_papers.return_value = [
            {"arxiv_id": "2401.00001", "score": 3, "skip_reason": "off-topic", "processed": False},
        ]

        result = fetch_scored_papers()

        assert len(result) == 1


@patch.dict(os.environ, {"NOTION_API_KEY": "test-key", "NOTION_DATABASE_ID": "test-db-id"})
class TestMarkPapersProcessed:
    @patch("notion_utils.Client", create=True)
    def test_marks_each_page(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client

        mark_papers_processed(["page-aaa", "page-bbb"])

        assert mock_client.pages.update.call_count == 2
        mock_client.pages.update.assert_any_call(
            page_id="page-aaa",
            properties={"Processed": {"checkbox": True}},
        )
        mock_client.pages.update.assert_any_call(
            page_id="page-bbb",
            properties={"Processed": {"checkbox": True}},
        )

    @patch("notion_utils.Client", create=True)
    def test_empty_list_does_nothing(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client

        mark_papers_processed([])

        mock_client.pages.update.assert_not_called()

    @patch("notion_utils.Client", create=True)
    def test_continues_on_failure(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.update.side_effect = [
            Exception("API error"),
            None,
        ]

        # Should not raise
        mark_papers_processed(["page-aaa", "page-bbb"])

        assert mock_client.pages.update.call_count == 2


@patch.dict(os.environ, {"NOTION_API_KEY": "test-key", "NOTION_DATABASE_ID": "test-db-id"})
class TestRoundTrip:
    @patch("notion_utils.Client", create=True)
    def test_push_then_fetch_papers(self, mock_notion_cls):
        mock_client = MagicMock()
        mock_notion_cls.return_value = mock_client
        mock_client.pages.create.return_value = {"id": "page-123"}
        mock_client.databases.query.return_value = {
            "results": [_make_notion_page("2401.99999", "Round Trip Paper", processed=False)],
            "has_more": False,
        }

        paper = _make_filtered_paper("2401.99999")
        paper.title = "Round Trip Paper"

        push_papers([paper], run_id="2024-01-15T07:00:00Z")
        fetched = fetch_papers()

        arxiv_ids = [p["arxiv_id"] for p in fetched]
        titles = [p["title"] for p in fetched]
        assert "2401.99999" in arxiv_ids
        assert "Round Trip Paper" in titles
