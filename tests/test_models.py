import pytest
from pydantic import ValidationError

from models import FilteredPaper, Paper, PreferencesUpdate


class TestPaper:
    def test_paper_valid_construction(self):
        paper = Paper(
            arxiv_id="2401.12345",
            title="Test Paper",
            abstract="An abstract",
            url="http://arxiv.org/abs/2401.12345",
        )
        assert paper.arxiv_id == "2401.12345"
        assert paper.title == "Test Paper"
        assert paper.abstract == "An abstract"
        assert paper.url == "http://arxiv.org/abs/2401.12345"

    def test_paper_missing_field_raises(self):
        with pytest.raises(ValidationError):
            Paper(
                arxiv_id="2401.12345",
                title="Test Paper",
                # missing abstract and url
            )


class TestFilteredPaper:
    def test_filtered_paper_valid(self):
        fp = FilteredPaper(
            arxiv_id="2401.12345",
            title="Test Paper",
            abstract="An abstract",
            url="http://arxiv.org/abs/2401.12345",
            reason="Relevant to interests",
            is_wildcard=False,
        )
        assert fp.is_wildcard is False

        fp_wildcard = FilteredPaper(
            arxiv_id="2401.12346",
            title="Wildcard Paper",
            abstract="An abstract",
            url="http://arxiv.org/abs/2401.12346",
            reason="Exploration pick",
            is_wildcard=True,
        )
        assert fp_wildcard.is_wildcard is True

    def test_filtered_paper_missing_reason_raises(self):
        with pytest.raises(ValidationError):
            FilteredPaper(
                arxiv_id="2401.12345",
                title="Test Paper",
                abstract="An abstract",
                url="http://arxiv.org/abs/2401.12345",
                # missing reason
                is_wildcard=False,
            )


class TestPreferencesUpdate:
    def test_preferences_update_valid(self):
        update = PreferencesUpdate(
            updated_interests=[],
            updated_avoid=[],
            updated_summary="No changes",
            wildcard_promoted=[],
        )
        assert update.updated_interests == []
        assert update.updated_summary == "No changes"

    def test_preferences_update_missing_field_raises(self):
        with pytest.raises(ValidationError):
            PreferencesUpdate(
                updated_interests=["topic"],
                updated_avoid=["other"],
                # missing updated_summary
                wildcard_promoted=[],
            )
