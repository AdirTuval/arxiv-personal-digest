import logging
from pathlib import Path

import anthropic
import yaml

from models import PreferencesUpdate

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES_PATH = Path(__file__).resolve().parent.parent / "preferences.yaml"


def update_preferences(
    scored_papers: list[dict],
    preferences_path: Path = DEFAULT_PREFERENCES_PATH,
) -> PreferencesUpdate:
    """Read scored papers and use Claude to update preferences.yaml.

    Loads the current preferences, sends them along with scored papers
    to Claude, and writes back the updated file. Respects immutable
    fields (immutable_interests, field, max_results_per_run,
    max_papers_to_push, example_papers).

    Args:
        scored_papers: Dicts from notion_utils.fetch_scored_papers().
        preferences_path: Path to preferences.yaml.

    Returns:
        A PreferencesUpdate describing the changes made.
    """
    raise NotImplementedError
