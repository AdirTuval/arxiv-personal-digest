import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fetcher import fetch_new_papers, load_seen_papers, save_seen_papers
from models import Paper


class TestLoadSeenPapers:
    def test_load_seen_papers_existing_file(self, tmp_path):
        path = tmp_path / "seen.json"
        ids = ["2401.11111", "2401.22222"]
        path.write_text(json.dumps(ids))

        result = load_seen_papers(path)

        assert isinstance(result, set)
        assert result == {"2401.11111", "2401.22222"}

    def test_load_seen_papers_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"

        result = load_seen_papers(path)

        assert result == set()

    def test_load_seen_papers_empty_file(self, tmp_path):
        path = tmp_path / "seen.json"
        path.write_text("[]")

        result = load_seen_papers(path)

        assert result == set()


class TestSaveSeenPapers:
    def test_save_seen_papers_writes_json(self, tmp_path):
        path = tmp_path / "seen.json"
        seen = {"2401.12345", "2401.12346"}

        save_seen_papers(path, seen)

        data = json.loads(path.read_text())
        assert sorted(data) == sorted(seen)

    def test_save_seen_papers_overwrites(self, tmp_path):
        path = tmp_path / "seen.json"
        path.write_text(json.dumps(["old_id"]))

        new_seen = {"2401.99999"}
        save_seen_papers(path, new_seen)

        data = json.loads(path.read_text())
        assert data == ["2401.99999"]


class TestFetchNewPapers:
    @patch("fetcher.fetch_papers")
    def test_fetch_new_papers_filters_seen(self, mock_fetch, tmp_path):
        seen_path = tmp_path / "seen.json"
        seen_path.write_text(json.dumps(["2401.12345"]))

        mock_fetch.return_value = [
            Paper(arxiv_id="2401.12345", title="Seen", abstract="A", url="u1"),
            Paper(arxiv_id="2401.12346", title="New1", abstract="B", url="u2"),
            Paper(arxiv_id="2401.12347", title="New2", abstract="C", url="u3"),
        ]

        result = fetch_new_papers("cs.AI", 50, seen_papers_path=seen_path)

        assert len(result) == 2
        assert all(p.arxiv_id != "2401.12345" for p in result)

    @patch("fetcher.fetch_papers")
    def test_fetch_new_papers_all_seen(self, mock_fetch, tmp_path):
        seen_path = tmp_path / "seen.json"
        seen_path.write_text(json.dumps(["2401.12345", "2401.12346"]))

        mock_fetch.return_value = [
            Paper(arxiv_id="2401.12345", title="P1", abstract="A", url="u1"),
            Paper(arxiv_id="2401.12346", title="P2", abstract="B", url="u2"),
        ]

        result = fetch_new_papers("cs.AI", 50, seen_papers_path=seen_path)

        assert result == []

    @patch("fetcher.fetch_papers")
    def test_fetch_new_papers_none_seen(self, mock_fetch, tmp_path):
        seen_path = tmp_path / "nonexistent.json"

        mock_fetch.return_value = [
            Paper(arxiv_id="2401.12345", title="P1", abstract="A", url="u1"),
            Paper(arxiv_id="2401.12346", title="P2", abstract="B", url="u2"),
        ]

        result = fetch_new_papers("cs.AI", 50, seen_papers_path=seen_path)

        assert len(result) == 2
