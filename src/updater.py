import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

import llm
import pdf_extract
from models import PreferencesUpdate

logger = logging.getLogger(__name__)

DEFAULT_PREFERENCES_PATH = Path(__file__).resolve().parent.parent / "preferences.yaml"
HISTORICAL_DIR = Path(__file__).resolve().parent.parent / "historical_preferences"


def _save_historical_snapshot(preferences_path: Path) -> Path:
    """Copy the current preferences file to a timestamped snapshot.

    Returns:
        Path to the snapshot file.
    """
    HISTORICAL_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_path = HISTORICAL_DIR / f"preferences_{timestamp}.yaml"
    shutil.copy2(preferences_path, snapshot_path)
    logger.info("Saved preferences snapshot to %s", snapshot_path)
    return snapshot_path


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
    current_prefs = yaml.safe_load(preferences_path.read_text())

    if not scored_papers:
        return PreferencesUpdate(
            updated_interests=current_prefs.get("interests", []),
            updated_avoid=current_prefs.get("avoid", []),
            updated_summary=current_prefs.get("scoring_history_summary", ""),
            wildcard_promoted=[],
        )

    _save_historical_snapshot(preferences_path)

    arxiv_ids = [p["arxiv_id"] for p in scored_papers]
    paper_full_texts = pdf_extract.fetch_paper_full_texts(arxiv_ids)

    update = llm.update_preferences_llm(scored_papers, current_prefs, paper_full_texts)

    # Apply mutable fields only
    current_prefs["interests"] = update.updated_interests
    current_prefs["avoid"] = update.updated_avoid
    current_prefs["scoring_history_summary"] = update.updated_summary

    # Add wildcard-promoted topics to interests
    for topic in update.wildcard_promoted:
        if topic not in current_prefs["interests"]:
            current_prefs["interests"].append(topic)

    preferences_path.write_text(yaml.dump(current_prefs, default_flow_style=False))
    logger.info("Updated preferences.yaml")

    return update
