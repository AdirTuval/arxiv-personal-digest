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


def _make_claude_response(papers, wildcard_idx=None):
    """Build a mock Claude response JSON with filtered papers."""
    results = []
    for i, p in enumerate(papers):
        results.append(
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "abstract": p.abstract,
                "url": p.url,
                "reason": f"Relevant because of topic {i}",
                "is_wildcard": i == wildcard_idx,
            }
        )
    return json.dumps(results)


class TestFilterPapers:
    @patch("filter.anthropic.Anthropic")
    def test_filter_papers_returns_filtered_papers(
        self, mock_anthropic_cls, sample_preferences
    ):
        papers = _make_papers(5)
        selected = papers[:3]

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text=_make_claude_response(selected, wildcard_idx=2))
        ]
        mock_client.messages.create.return_value = mock_msg

        result = filter_papers(papers, sample_preferences)

        assert isinstance(result, list)
        assert all(isinstance(fp, FilteredPaper) for fp in result)
        assert len(result) > 0
        assert all(fp.reason for fp in result)

    @patch("filter.anthropic.Anthropic")
    def test_filter_papers_respects_max_papers(
        self, mock_anthropic_cls, sample_preferences
    ):
        sample_preferences["max_papers_to_push"] = 2
        papers = _make_papers(10)
        selected = papers[:2]

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text=_make_claude_response(selected))
        ]
        mock_client.messages.create.return_value = mock_msg

        result = filter_papers(papers, sample_preferences)

        assert len(result) <= sample_preferences["max_papers_to_push"]

    @patch("filter.anthropic.Anthropic")
    def test_filter_papers_includes_wildcard(
        self, mock_anthropic_cls, sample_preferences
    ):
        papers = _make_papers(5)
        selected = papers[:3]

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text=_make_claude_response(selected, wildcard_idx=2))
        ]
        mock_client.messages.create.return_value = mock_msg

        result = filter_papers(papers, sample_preferences)

        wildcards = [fp for fp in result if fp.is_wildcard]
        assert len(wildcards) >= 1

    @patch("filter.anthropic.Anthropic")
    def test_filter_papers_empty_input(self, mock_anthropic_cls, sample_preferences):
        result = filter_papers([], sample_preferences)

        assert result == []

    @patch("filter.anthropic.Anthropic")
    def test_filter_papers_no_exploration(
        self, mock_anthropic_cls, sample_preferences
    ):
        sample_preferences["exploration"]["enabled"] = False
        papers = _make_papers(5)
        selected = papers[:2]

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text=_make_claude_response(selected, wildcard_idx=None)
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        result = filter_papers(papers, sample_preferences)

        wildcards = [fp for fp in result if fp.is_wildcard]
        assert len(wildcards) == 0

    @patch("filter.anthropic.Anthropic")
    def test_filter_papers_sends_preferences_to_claude(
        self, mock_anthropic_cls, sample_preferences
    ):
        papers = _make_papers(3)
        selected = papers[:2]

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text=_make_claude_response(selected))
        ]
        mock_client.messages.create.return_value = mock_msg

        filter_papers(papers, sample_preferences)

        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args
        # The prompt should contain preferences and paper abstracts
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        prompt_text = str(messages)
        assert "interests" in prompt_text.lower() or "preferences" in prompt_text.lower()
