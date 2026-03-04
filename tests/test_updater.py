import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from models import PreferencesUpdate
from updater import update_preferences


def _make_claude_update_response(
    interests=None, avoid=None, summary="Updated summary", wildcard_promoted=None
):
    """Build a mock Claude response for preferences update."""
    return json.dumps(
        {
            "updated_interests": interests or ["RAG systems", "LLM fine-tuning"],
            "updated_avoid": avoid or ["Pure benchmarks"],
            "updated_summary": summary,
            "wildcard_promoted": wildcard_promoted or [],
        }
    )


class TestUpdatePreferences:
    @patch("updater.anthropic.Anthropic")
    def test_update_preferences_returns_update(
        self, mock_anthropic_cls, preferences_file, sample_scored_papers
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text=_make_claude_update_response())
        ]
        mock_client.messages.create.return_value = mock_msg

        result = update_preferences(sample_scored_papers, preferences_path=preferences_file)

        assert isinstance(result, PreferencesUpdate)
        assert isinstance(result.updated_interests, list)
        assert isinstance(result.updated_avoid, list)
        assert isinstance(result.updated_summary, str)

    @patch("updater.anthropic.Anthropic")
    def test_update_preferences_no_scored_papers(
        self, mock_anthropic_cls, preferences_file
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text=_make_claude_update_response(
                    interests=["RAG and retrieval systems for production use",
                               "LLM fine-tuning on limited hardware"],
                    avoid=["Pure benchmark papers with no practical application",
                           "Vision-only models unrelated to language"],
                    summary="",
                    wildcard_promoted=[],
                )
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        result = update_preferences([], preferences_path=preferences_file)

        # With no scored papers, interests and avoid should remain unchanged
        prefs = yaml.safe_load(preferences_file.read_text())
        assert "interests" in prefs

    @patch("updater.anthropic.Anthropic")
    def test_update_preferences_preserves_immutable(
        self, mock_anthropic_cls, preferences_file, sample_scored_papers
    ):
        original = yaml.safe_load(preferences_file.read_text())
        original_immutable = original["immutable_interests"]
        original_field = original["field"]
        original_max_results = original["max_results_per_run"]
        original_max_push = original["max_papers_to_push"]
        original_examples = original["example_papers"]

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(text=_make_claude_update_response())
        ]
        mock_client.messages.create.return_value = mock_msg

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        updated = yaml.safe_load(preferences_file.read_text())
        assert updated["immutable_interests"] == original_immutable
        assert updated["field"] == original_field
        assert updated["max_results_per_run"] == original_max_results
        assert updated["max_papers_to_push"] == original_max_push
        assert updated["example_papers"] == original_examples

    @patch("updater.anthropic.Anthropic")
    def test_update_preferences_writes_yaml(
        self, mock_anthropic_cls, preferences_file, sample_scored_papers
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text=_make_claude_update_response(
                    interests=["New topic A", "New topic B"]
                )
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        updated = yaml.safe_load(preferences_file.read_text())
        assert "interests" in updated
        assert updated["interests"] == ["New topic A", "New topic B"]

    @patch("updater.anthropic.Anthropic")
    def test_update_preferences_updates_summary(
        self, mock_anthropic_cls, preferences_file, sample_scored_papers
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text=_make_claude_update_response(
                    summary="User prefers practical LLM papers over theoretical ones"
                )
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        updated = yaml.safe_load(preferences_file.read_text())
        assert updated["scoring_history_summary"] == "User prefers practical LLM papers over theoretical ones"

    @patch("updater.anthropic.Anthropic")
    def test_update_preferences_promotes_wildcard(
        self, mock_anthropic_cls, preferences_file, sample_scored_papers
    ):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [
            MagicMock(
                text=_make_claude_update_response(
                    wildcard_promoted=["Human-AI interaction design"]
                )
            )
        ]
        mock_client.messages.create.return_value = mock_msg

        result = update_preferences(sample_scored_papers, preferences_path=preferences_file)

        assert "Human-AI interaction design" in result.wildcard_promoted
