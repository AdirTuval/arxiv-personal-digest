import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest
import yaml

from models import FilteredPaper, Paper, PreferencesUpdate


class TestRun:
    @patch("main.notion_utils")
    @patch("main.filter")
    @patch("main.fetcher")
    @patch("main.updater")
    @patch("main.yaml.safe_load")
    @patch("main.Path.read_text")
    def test_run_calls_all_steps_in_order(
        self,
        mock_read_text,
        mock_yaml_load,
        mock_updater,
        mock_fetcher,
        mock_filter,
        mock_notion,
    ):
        from main import run

        mock_notion.fetch_scored_papers.return_value = []
        mock_updater.update_preferences.return_value = PreferencesUpdate(
            updated_interests=[], updated_avoid=[], updated_summary="", wildcard_promoted=[]
        )
        mock_yaml_load.return_value = {
            "field": "cs.AI",
            "max_results_per_run": 50,
            "max_papers_to_push": 5,
        }
        mock_fetcher.fetch_new_papers.return_value = [
            Paper(arxiv_id="2401.12345", title="P1", abstract="A", url="u1")
        ]
        mock_filter.filter_papers.return_value = [
            FilteredPaper(
                arxiv_id="2401.12345", title="P1", abstract="A",
                url="u1", reason="r", short_summary="s", is_wildcard=False,
            )
        ]
        mock_notion.push_papers.return_value = ["2401.12345"]

        run()

        # All steps must be called
        mock_notion.fetch_scored_papers.assert_called_once()
        mock_updater.update_preferences.assert_called_once()
        mock_fetcher.fetch_new_papers.assert_called_once()
        mock_filter.filter_papers.assert_called_once()
        mock_notion.push_papers.assert_called_once()

    @patch("main.notion_utils")
    @patch("main.filter")
    @patch("main.fetcher")
    @patch("main.updater")
    @patch("main.yaml.safe_load")
    @patch("main.Path.read_text")
    def test_run_passes_scored_papers_to_updater(
        self,
        mock_read_text,
        mock_yaml_load,
        mock_updater,
        mock_fetcher,
        mock_filter,
        mock_notion,
    ):
        from main import run

        scored = [{"arxiv_id": "2401.12345", "title": "P", "score": 5}]
        mock_notion.fetch_scored_papers.return_value = scored
        mock_updater.update_preferences.return_value = PreferencesUpdate(
            updated_interests=[], updated_avoid=[], updated_summary="", wildcard_promoted=[]
        )
        mock_yaml_load.return_value = {
            "field": "cs.AI", "max_results_per_run": 50, "max_papers_to_push": 5
        }
        mock_fetcher.fetch_new_papers.return_value = []

        run()

        # updater should receive the scored papers from notion
        update_call = mock_updater.update_preferences.call_args
        args = update_call[0] if update_call[0] else []
        kwargs = update_call[1] if update_call[1] else {}
        passed_scored = args[0] if args else kwargs.get("scored_papers", [])
        assert passed_scored == scored

    @patch("main.notion_utils")
    @patch("main.filter")
    @patch("main.fetcher")
    @patch("main.updater")
    @patch("main.yaml.safe_load")
    @patch("main.Path.read_text")
    def test_run_passes_preferences_to_filter(
        self,
        mock_read_text,
        mock_yaml_load,
        mock_updater,
        mock_fetcher,
        mock_filter,
        mock_notion,
    ):
        from main import run

        prefs = {
            "field": "cs.AI",
            "max_results_per_run": 50,
            "max_papers_to_push": 5,
            "interests": ["RAG"],
        }
        mock_notion.fetch_scored_papers.return_value = []
        mock_updater.update_preferences.return_value = PreferencesUpdate(
            updated_interests=[], updated_avoid=[], updated_summary="", wildcard_promoted=[]
        )
        mock_yaml_load.return_value = prefs
        mock_fetcher.fetch_new_papers.return_value = [
            Paper(arxiv_id="2401.12345", title="P1", abstract="A", url="u1")
        ]
        mock_filter.filter_papers.return_value = []
        mock_notion.push_papers.return_value = []

        run()

        filter_call = mock_filter.filter_papers.call_args
        args = filter_call[0] if filter_call[0] else []
        kwargs = filter_call[1] if filter_call[1] else {}
        passed_prefs = args[1] if len(args) > 1 else kwargs.get("preferences", {})
        assert passed_prefs == prefs

    @patch("main.notion_utils")
    @patch("main.filter")
    @patch("main.fetcher")
    @patch("main.updater")
    @patch("main.yaml.safe_load")
    @patch("main.Path.read_text")
    def test_run_updates_seen_papers_after_push(
        self,
        mock_read_text,
        mock_yaml_load,
        mock_updater,
        mock_fetcher,
        mock_filter,
        mock_notion,
    ):
        from main import run

        mock_notion.fetch_scored_papers.return_value = []
        mock_updater.update_preferences.return_value = PreferencesUpdate(
            updated_interests=[], updated_avoid=[], updated_summary="", wildcard_promoted=[]
        )
        mock_yaml_load.return_value = {
            "field": "cs.AI", "max_results_per_run": 50, "max_papers_to_push": 5
        }
        mock_fetcher.fetch_new_papers.return_value = [
            Paper(arxiv_id="2401.12345", title="P1", abstract="A", url="u1")
        ]
        mock_fetcher.load_seen_papers.return_value = set()
        mock_filter.filter_papers.return_value = [
            FilteredPaper(
                arxiv_id="2401.12345", title="P1", abstract="A",
                url="u1", reason="r", short_summary="s", is_wildcard=False,
            )
        ]
        pushed_ids = ["2401.12345"]
        mock_notion.push_papers.return_value = pushed_ids

        run()

        # save_seen_papers should be called with pushed IDs
        mock_fetcher.save_seen_papers.assert_called_once()
        save_call = mock_fetcher.save_seen_papers.call_args
        args = save_call[0] if save_call[0] else []
        kwargs = save_call[1] if save_call[1] else {}
        saved_ids = args[1] if len(args) > 1 else kwargs.get("seen", set())
        assert "2401.12345" in saved_ids

    @patch("main.notion_utils")
    @patch("main.filter")
    @patch("main.fetcher")
    @patch("main.updater")
    @patch("main.yaml.safe_load")
    @patch("main.Path.read_text")
    def test_run_no_new_papers_skips_filter_and_push(
        self,
        mock_read_text,
        mock_yaml_load,
        mock_updater,
        mock_fetcher,
        mock_filter,
        mock_notion,
    ):
        from main import run

        mock_notion.fetch_scored_papers.return_value = []
        mock_updater.update_preferences.return_value = PreferencesUpdate(
            updated_interests=[], updated_avoid=[], updated_summary="", wildcard_promoted=[]
        )
        mock_yaml_load.return_value = {
            "field": "cs.AI", "max_results_per_run": 50, "max_papers_to_push": 5
        }
        mock_fetcher.fetch_new_papers.return_value = []

        run()

        mock_filter.filter_papers.assert_not_called()
        mock_notion.push_papers.assert_not_called()

    @patch("main.notion_utils")
    @patch("main.filter")
    @patch("main.fetcher")
    @patch("main.updater")
    @patch("main.yaml.safe_load")
    @patch("main.Path.read_text")
    def test_run_updater_failure_continues(
        self,
        mock_read_text,
        mock_yaml_load,
        mock_updater,
        mock_fetcher,
        mock_filter,
        mock_notion,
    ):
        from main import run

        mock_notion.fetch_scored_papers.return_value = []
        mock_updater.update_preferences.side_effect = RuntimeError("Claude failed")
        mock_yaml_load.return_value = {
            "field": "cs.AI", "max_results_per_run": 50, "max_papers_to_push": 5
        }
        mock_fetcher.fetch_new_papers.return_value = [
            Paper(arxiv_id="2401.12345", title="P1", abstract="A", url="u1")
        ]
        mock_filter.filter_papers.return_value = [
            FilteredPaper(
                arxiv_id="2401.12345", title="P1", abstract="A",
                url="u1", reason="r", short_summary="s", is_wildcard=False,
            )
        ]
        mock_notion.push_papers.return_value = ["2401.12345"]

        # Should not raise despite updater failure
        run()

        # Rest of pipeline still executed
        mock_fetcher.fetch_new_papers.assert_called_once()
        mock_filter.filter_papers.assert_called_once()
        mock_notion.push_papers.assert_called_once()
