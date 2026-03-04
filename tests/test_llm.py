import json
from unittest.mock import MagicMock, patch

import pytest

from llm import (
    _call_claude,
    _parse_json_with_retry,
    _truncate_text,
    filter_papers_llm,
    update_preferences_llm,
)
from models import FilteredPaper, Paper, PreferencesUpdate


def _mock_anthropic(response_text):
    """Create a mock Anthropic client that returns the given text."""
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestCallClaude:
    @patch("llm.anthropic.Anthropic")
    def test_call_claude_returns_text(self, mock_cls):
        mock_cls.return_value = _mock_anthropic("Hello response")

        result = _call_claude("system prompt", "user prompt")

        assert result == "Hello response"

    @patch("llm.anthropic.Anthropic")
    def test_call_claude_passes_params(self, mock_cls):
        client = _mock_anthropic("ok")
        mock_cls.return_value = client

        _call_claude("sys", "usr", max_tokens=1024)

        client.messages.create.assert_called_once()
        call_kwargs = client.messages.create.call_args
        assert call_kwargs.kwargs["system"] == "sys"
        assert call_kwargs.kwargs["max_tokens"] == 1024
        assert call_kwargs.kwargs["messages"] == [{"role": "user", "content": "usr"}]


class TestParseJsonWithRetry:
    @patch("llm._call_claude")
    def test_valid_json_first_try(self, mock_call):
        mock_call.return_value = '{"key": "value"}'

        result = _parse_json_with_retry("sys", "usr")

        assert result == {"key": "value"}
        assert mock_call.call_count == 1

    @patch("llm._call_claude")
    def test_retry_on_invalid_json(self, mock_call):
        mock_call.side_effect = [
            "Not valid JSON here",
            '{"key": "fixed"}',
        ]

        result = _parse_json_with_retry("sys", "usr")

        assert result == {"key": "fixed"}
        assert mock_call.call_count == 2

    @patch("llm._call_claude")
    def test_raises_after_both_failures(self, mock_call):
        mock_call.side_effect = [
            "not json",
            "still not json",
        ]

        with pytest.raises(ValueError, match="Failed to parse JSON after retry"):
            _parse_json_with_retry("sys", "usr")


class TestTruncateText:
    def test_short_text_unchanged(self):
        assert _truncate_text("hello world", max_words=10) == "hello world"

    def test_long_text_truncated(self):
        text = " ".join(f"word{i}" for i in range(100))
        result = _truncate_text(text, max_words=10)
        assert result.endswith("[truncated]")
        # 10 words + "[truncated]"
        assert len(result.split()) == 11

    def test_exact_limit_unchanged(self):
        text = "one two three"
        assert _truncate_text(text, max_words=3) == "one two three"


class TestFilterPapersLlm:
    @patch("llm._parse_json_with_retry")
    def test_returns_filtered_papers(self, mock_parse, sample_preferences):
        mock_parse.return_value = [
            {
                "arxiv_id": "2401.12345",
                "title": "Paper 1",
                "abstract": "Abstract 1",
                "url": "http://arxiv.org/abs/2401.12345",
                "reason": "Relevant to interests",
                "short_summary": "A summary of paper 1.",
                "is_wildcard": False,
            },
            {
                "arxiv_id": "2401.12346",
                "title": "Paper 2",
                "abstract": "Abstract 2",
                "url": "http://arxiv.org/abs/2401.12346",
                "reason": "Wildcard pick",
                "short_summary": "A summary of paper 2.",
                "is_wildcard": True,
            },
        ]

        papers = [
            Paper(arxiv_id=f"2401.{12345+i:05d}", title=f"Paper {i}",
                  abstract=f"Abstract {i}", url=f"http://arxiv.org/abs/2401.{12345+i:05d}")
            for i in range(5)
        ]

        result = filter_papers_llm(papers, sample_preferences)

        assert len(result) == 2
        assert all(isinstance(fp, FilteredPaper) for fp in result)
        assert result[0].reason == "Relevant to interests"
        assert result[0].short_summary == "A summary of paper 1."
        assert result[1].is_wildcard is True

    @patch("llm._parse_json_with_retry")
    def test_prompt_contains_preferences(self, mock_parse, sample_preferences):
        mock_parse.return_value = []

        papers = [
            Paper(arxiv_id="2401.12345", title="P", abstract="A",
                  url="http://arxiv.org/abs/2401.12345")
        ]

        filter_papers_llm(papers, sample_preferences)

        call_args = mock_parse.call_args
        user_prompt = call_args[0][1]  # second positional arg
        assert "interests" in user_prompt
        assert "RAG and retrieval systems" in user_prompt

    @patch("llm._parse_json_with_retry")
    def test_wildcard_instruction_when_exploration_enabled(self, mock_parse, sample_preferences):
        mock_parse.return_value = []

        papers = [
            Paper(arxiv_id="2401.12345", title="P", abstract="A",
                  url="http://arxiv.org/abs/2401.12345")
        ]

        filter_papers_llm(papers, sample_preferences)

        user_prompt = mock_parse.call_args[0][1]
        assert "wildcard" in user_prompt.lower()

    @patch("llm._parse_json_with_retry")
    def test_no_wildcard_instruction_when_exploration_disabled(self, mock_parse, sample_preferences):
        sample_preferences["exploration"]["enabled"] = False
        mock_parse.return_value = []

        papers = [
            Paper(arxiv_id="2401.12345", title="P", abstract="A",
                  url="http://arxiv.org/abs/2401.12345")
        ]

        filter_papers_llm(papers, sample_preferences)

        user_prompt = mock_parse.call_args[0][1]
        # The wildcard selection instruction should not appear
        assert "select exactly" not in user_prompt.lower()
        assert "wildcard paper" not in user_prompt.lower()


class TestUpdatePreferencesLlm:
    @patch("llm._parse_json_with_retry")
    def test_returns_preferences_update(self, mock_parse, sample_preferences, sample_scored_papers):
        mock_parse.return_value = {
            "updated_interests": ["RAG systems", "LLM fine-tuning"],
            "updated_avoid": ["Pure benchmarks"],
            "updated_summary": "User prefers practical papers",
            "wildcard_promoted": ["HCI topics"],
        }

        result = update_preferences_llm(
            sample_scored_papers, sample_preferences, {}
        )

        assert isinstance(result, PreferencesUpdate)
        assert result.updated_interests == ["RAG systems", "LLM fine-tuning"]
        assert result.updated_avoid == ["Pure benchmarks"]
        assert result.updated_summary == "User prefers practical papers"
        assert result.wildcard_promoted == ["HCI topics"]

    @patch("llm._parse_json_with_retry")
    def test_includes_full_text_in_prompt(self, mock_parse, sample_preferences, sample_scored_papers):
        mock_parse.return_value = {
            "updated_interests": [],
            "updated_avoid": [],
            "updated_summary": "",
            "wildcard_promoted": [],
        }

        full_texts = {"2401.12345": "Full text of paper about inference optimization."}

        update_preferences_llm(sample_scored_papers, sample_preferences, full_texts)

        user_prompt = mock_parse.call_args[0][1]
        assert "full_text" in user_prompt

    @patch("llm._parse_json_with_retry")
    def test_truncates_full_text(self, mock_parse, sample_preferences, sample_scored_papers):
        mock_parse.return_value = {
            "updated_interests": [],
            "updated_avoid": [],
            "updated_summary": "",
            "wildcard_promoted": [],
        }

        # Create text exceeding MAX_WORDS_PER_PAPER
        long_text = " ".join(f"word{i}" for i in range(5000))
        full_texts = {"2401.12345": long_text}

        update_preferences_llm(sample_scored_papers, sample_preferences, full_texts)

        user_prompt = mock_parse.call_args[0][1]
        assert "[truncated]" in user_prompt

    @patch("llm._parse_json_with_retry")
    def test_caps_full_text_papers(self, mock_parse):
        """Only MAX_PAPERS_WITH_FULL_TEXT papers get full text included."""
        mock_parse.return_value = {
            "updated_interests": [],
            "updated_avoid": [],
            "updated_summary": "",
            "wildcard_promoted": [],
        }

        scored = [
            {"arxiv_id": f"2401.{i:05d}", "title": f"Paper {i}",
             "score": 4, "skip_reason": None, "paper_type": "Regular"}
            for i in range(12)
        ]
        full_texts = {f"2401.{i:05d}": f"Text for paper {i}" for i in range(12)}
        prefs = {"interests": [], "avoid": [], "scoring_history_summary": ""}

        update_preferences_llm(scored, prefs, full_texts)

        user_prompt = mock_parse.call_args[0][1]
        # Count occurrences of "full_text" in the JSON data within the prompt
        assert user_prompt.count('"full_text"') <= 8
