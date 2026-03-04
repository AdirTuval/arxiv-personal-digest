import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from models import PreferencesUpdate
from updater import update_preferences


def _make_update(
    interests=None, avoid=None, summary="Updated summary", wildcard_promoted=None
):
    return PreferencesUpdate(
        updated_interests=interests or ["RAG systems", "LLM fine-tuning"],
        updated_avoid=avoid or ["Pure benchmarks"],
        updated_summary=summary,
        wildcard_promoted=wildcard_promoted or [],
    )


class TestUpdatePreferences:
    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_preferences_returns_update(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        mock_pdf.return_value = {}
        mock_llm.return_value = _make_update()

        result = update_preferences(sample_scored_papers, preferences_path=preferences_file)

        assert isinstance(result, PreferencesUpdate)
        assert isinstance(result.updated_interests, list)
        assert isinstance(result.updated_avoid, list)
        assert isinstance(result.updated_summary, str)

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_preferences_no_scored_papers(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file
    ):
        result = update_preferences([], preferences_path=preferences_file)

        # With no scored papers, no LLM call should be made
        mock_llm.assert_not_called()
        mock_pdf.assert_not_called()
        mock_snapshot.assert_not_called()

        # interests and avoid should remain unchanged
        prefs = yaml.safe_load(preferences_file.read_text())
        assert "interests" in prefs
        assert result.updated_interests == prefs["interests"]

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_preferences_preserves_immutable(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        original = yaml.safe_load(preferences_file.read_text())
        original_immutable = original["immutable_interests"]
        original_field = original["field"]
        original_max_results = original["max_results_per_run"]
        original_max_push = original["max_papers_to_push"]
        original_examples = original["example_papers"]

        mock_pdf.return_value = {}
        mock_llm.return_value = _make_update()

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        updated = yaml.safe_load(preferences_file.read_text())
        assert updated["immutable_interests"] == original_immutable
        assert updated["field"] == original_field
        assert updated["max_results_per_run"] == original_max_results
        assert updated["max_papers_to_push"] == original_max_push
        assert updated["example_papers"] == original_examples

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_preferences_writes_yaml(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        mock_pdf.return_value = {}
        mock_llm.return_value = _make_update(
            interests=["New topic A", "New topic B"]
        )

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        updated = yaml.safe_load(preferences_file.read_text())
        assert "interests" in updated
        assert updated["interests"] == ["New topic A", "New topic B"]

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_preferences_updates_summary(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        mock_pdf.return_value = {}
        mock_llm.return_value = _make_update(
            summary="User prefers practical LLM papers over theoretical ones"
        )

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        updated = yaml.safe_load(preferences_file.read_text())
        assert updated["scoring_history_summary"] == "User prefers practical LLM papers over theoretical ones"

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_preferences_promotes_wildcard(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        mock_pdf.return_value = {}
        mock_llm.return_value = _make_update(
            wildcard_promoted=["Human-AI interaction design"]
        )

        result = update_preferences(sample_scored_papers, preferences_path=preferences_file)

        assert "Human-AI interaction design" in result.wildcard_promoted
        # Wildcard topics should be added to interests in the YAML
        updated = yaml.safe_load(preferences_file.read_text())
        assert "Human-AI interaction design" in updated["interests"]

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_update_passes_full_texts_to_llm(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        full_texts = {"2401.12345": "Full paper text here"}
        mock_pdf.return_value = full_texts
        mock_llm.return_value = _make_update()

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        # LLM should receive the full texts
        call_kwargs = mock_llm.call_args
        assert call_kwargs[0][2] == full_texts  # third positional arg

    def test_save_historical_snapshot(self, preferences_file):
        from updater import _save_historical_snapshot

        snapshot_path = _save_historical_snapshot(preferences_file)

        assert snapshot_path.exists()
        assert snapshot_path.name.startswith("preferences_")
        assert snapshot_path.name.endswith(".yaml")
        # Content should match
        assert snapshot_path.read_text() == preferences_file.read_text()

    @patch("updater.pdf_extract.fetch_paper_full_texts")
    @patch("updater.llm.update_preferences_llm")
    @patch("updater._save_historical_snapshot")
    def test_snapshot_called_before_update(
        self, mock_snapshot, mock_llm, mock_pdf, preferences_file, sample_scored_papers
    ):
        mock_pdf.return_value = {}
        mock_llm.return_value = _make_update()

        update_preferences(sample_scored_papers, preferences_path=preferences_file)

        mock_snapshot.assert_called_once_with(preferences_file)
