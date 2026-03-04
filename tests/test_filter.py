import json
from unittest.mock import MagicMock, patch

import pytest

from filter import filter_papers
from models import FilteredPaper, Paper


def _make_papers(n=5):
    return [
        Paper(
            arxiv_id=f"2401.{12345 + i:05d}",
            title=f"Paper {i}",
            abstract=f"Abstract for paper {i}.",
            url=f"http://arxiv.org/abs/2401.{12345 + i:05d}",
        )
        for i in range(n)
    ]


def _make_filtered(papers, wildcard_idx=None):
    """Build FilteredPaper objects from a subset of papers."""
    return [
        FilteredPaper(
            arxiv_id=p.arxiv_id,
            title=p.title,
            abstract=p.abstract,
            url=p.url,
            reason=f"Relevant because of topic {i}",
            short_summary=f"Summary of paper {i}.",
            is_wildcard=i == wildcard_idx,
        )
        for i, p in enumerate(papers)
    ]


class TestFilterPapers:
    @patch("filter.llm.filter_papers_llm")
    def test_filter_papers_returns_filtered_papers(
        self, mock_llm, sample_preferences
    ):
        papers = _make_papers(5)
        selected = papers[:3]
        mock_llm.return_value = _make_filtered(selected, wildcard_idx=2)

        result = filter_papers(papers, sample_preferences)

        assert isinstance(result, list)
        assert all(isinstance(fp, FilteredPaper) for fp in result)
        assert len(result) == 3
        assert all(fp.reason for fp in result)
        assert all(fp.short_summary for fp in result)

    @patch("filter.llm.filter_papers_llm")
    def test_filter_papers_respects_max_papers(
        self, mock_llm, sample_preferences
    ):
        sample_preferences["max_papers_to_push"] = 2
        papers = _make_papers(10)
        selected = papers[:2]
        mock_llm.return_value = _make_filtered(selected)

        result = filter_papers(papers, sample_preferences)

        assert len(result) <= sample_preferences["max_papers_to_push"]

    @patch("filter.llm.filter_papers_llm")
    def test_filter_papers_includes_wildcard(
        self, mock_llm, sample_preferences
    ):
        papers = _make_papers(5)
        selected = papers[:3]
        mock_llm.return_value = _make_filtered(selected, wildcard_idx=2)

        result = filter_papers(papers, sample_preferences)

        wildcards = [fp for fp in result if fp.is_wildcard]
        assert len(wildcards) >= 1

    @patch("filter.llm.filter_papers_llm")
    def test_filter_papers_empty_input(self, mock_llm, sample_preferences):
        result = filter_papers([], sample_preferences)

        assert result == []
        mock_llm.assert_not_called()

    @patch("filter.llm.filter_papers_llm")
    def test_filter_papers_no_exploration(
        self, mock_llm, sample_preferences
    ):
        sample_preferences["exploration"]["enabled"] = False
        papers = _make_papers(5)
        selected = papers[:2]
        mock_llm.return_value = _make_filtered(selected, wildcard_idx=None)

        result = filter_papers(papers, sample_preferences)

        wildcards = [fp for fp in result if fp.is_wildcard]
        assert len(wildcards) == 0

    @patch("filter.llm.filter_papers_llm")
    def test_filter_papers_delegates_to_llm(
        self, mock_llm, sample_preferences
    ):
        papers = _make_papers(3)
        mock_llm.return_value = _make_filtered(papers[:2])

        filter_papers(papers, sample_preferences)

        mock_llm.assert_called_once_with(papers, sample_preferences)
