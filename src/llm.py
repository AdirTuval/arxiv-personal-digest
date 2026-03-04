import json
import logging
import os
import anthropic
import yaml

from models import FilteredPaper, PreferencesUpdate

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
MAX_WORDS_PER_PAPER = 3000
MAX_PAPERS_WITH_FULL_TEXT = 8


def _call_claude(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """Make a single Claude API call and return the text response."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _parse_json_with_retry(
    system: str, user: str, max_tokens: int = MAX_TOKENS
) -> any:
    """Call Claude expecting JSON. Retry once on parse failure.

    Raises:
        ValueError: If both attempts fail to produce valid JSON.
    """
    raw = _call_claude(system, user, max_tokens)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("First JSON parse failed, retrying with corrective prompt")

    corrective_user = (
        f"Your previous response was not valid JSON:\n\n{raw}\n\n"
        "Please return ONLY valid JSON with no markdown formatting, "
        "no code fences, and no extra text."
    )
    raw = _call_claude(system, corrective_user, max_tokens)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON after retry: {e}") from e


def filter_papers_llm(
    papers: list, preferences: dict
) -> list[FilteredPaper]:
    """Use Claude to select relevant papers and wildcards.

    Args:
        papers: List of Paper objects from arXiv.
        preferences: Full preferences dict from preferences.yaml.

    Returns:
        List of FilteredPaper objects with reason, short_summary, and is_wildcard.
    """
    max_papers = preferences.get("max_papers_to_push", 5)
    exploration = preferences.get("exploration", {})
    exploration_enabled = exploration.get("enabled", False)
    wildcard_count = exploration.get("wildcard_count", 1) if exploration_enabled else 0
    adjacent_categories = exploration.get("adjacent_categories", [])

    papers_data = []
    for p in papers:
        papers_data.append({
            "arxiv_id": p.arxiv_id,
            "title": p.title,
            "abstract": p.abstract,
            "url": p.url,
        })

    prefs_yaml = yaml.dump(preferences, default_flow_style=False)

    system = (
        "You are a research paper curator. Your job is to select the most relevant "
        "papers for the user based on their preferences. You must return valid JSON only, "
        "with no markdown formatting or code fences."
    )

    wildcard_instruction = ""
    if wildcard_count > 0:
        wildcard_instruction = (
            f"\n\nAdditionally, select exactly {wildcard_count} wildcard paper(s) from "
            f"categories adjacent to the user's main field ({adjacent_categories}). "
            "Wildcard papers should be surprising but potentially interesting — they expand "
            "the user's horizons. Mark wildcard papers with \"is_wildcard\": true."
        )

    user = (
        f"## User Preferences\n\n```yaml\n{prefs_yaml}```\n\n"
        f"## Papers to evaluate\n\n```json\n{json.dumps(papers_data, indent=2)}```\n\n"
        f"## Instructions\n\n"
        f"Select up to {max_papers} of the most relevant papers based on the user's "
        f"interests, immutable_interests, and avoid list. For each selected paper, explain "
        f"why it was selected (reason) and write a 2-3 sentence plain-English summary "
        f"(short_summary) that a non-expert could understand."
        f"{wildcard_instruction}\n\n"
        f"Return a JSON array of objects with these fields:\n"
        f"- arxiv_id (string)\n"
        f"- title (string)\n"
        f"- abstract (string)\n"
        f"- url (string)\n"
        f"- reason (string): why this paper was selected\n"
        f"- short_summary (string): 2-3 sentence plain-English summary\n"
        f"- is_wildcard (boolean): true only for wildcard picks\n\n"
        f"Return ONLY the JSON array, no other text."
    )

    data = _parse_json_with_retry(system, user)

    results = []
    for item in data:
        results.append(
            FilteredPaper(
                arxiv_id=item["arxiv_id"],
                title=item["title"],
                abstract=item["abstract"],
                url=item["url"],
                reason=item["reason"],
                short_summary=item["short_summary"],
                is_wildcard=item.get("is_wildcard", False),
            )
        )
    return results


def _truncate_text(text: str, max_words: int = MAX_WORDS_PER_PAPER) -> str:
    """Truncate text to a maximum number of words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [truncated]"


def update_preferences_llm(
    scored_papers: list[dict],
    current_preferences: dict,
    paper_full_texts: dict[str, str],
) -> PreferencesUpdate:
    """Use Claude to update preferences based on scored papers.

    Args:
        scored_papers: Dicts with arxiv_id, title, score, skip_reason, paper_type.
        current_preferences: Full preferences dict from preferences.yaml.
        paper_full_texts: Dict mapping arxiv_id to extracted full text.

    Returns:
        PreferencesUpdate with updated interests, avoid, summary, and wildcard promotions.
    """
    papers_info = []
    full_text_count = 0
    for paper in scored_papers:
        entry = {
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "score": paper.get("score"),
            "skip_reason": paper.get("skip_reason"),
            "paper_type": paper.get("paper_type", "Regular"),
        }
        arxiv_id = paper["arxiv_id"]
        if full_text_count < MAX_PAPERS_WITH_FULL_TEXT and paper_full_texts.get(arxiv_id):
            entry["full_text"] = _truncate_text(paper_full_texts[arxiv_id])
            full_text_count += 1
        papers_info.append(entry)

    prefs_yaml = yaml.dump(current_preferences, default_flow_style=False)

    system = (
        "You are helping curate a personal arXiv paper feed. Based on the user's "
        "scored papers and current preferences, update the preference profile. "
        "You must return valid JSON only, with no markdown formatting or code fences."
    )

    user = (
        f"## Current Preferences\n\n```yaml\n{prefs_yaml}```\n\n"
        f"## Scored Papers\n\n```json\n{json.dumps(papers_info, indent=2)}```\n\n"
        f"## Instructions\n\n"
        f"Based on the user's scores (1-5, higher = more liked) and skip reasons, "
        f"update the preferences:\n\n"
        f"1. **updated_interests**: Revise the interests list. Add topics from "
        f"highly-scored papers, refine existing interests, remove interests that "
        f"consistently get low scores. Do NOT include anything from immutable_interests.\n"
        f"2. **updated_avoid**: Revise the avoid list based on skip reasons and "
        f"low-scoring patterns.\n"
        f"3. **updated_summary**: Write a brief summary of the user's scoring patterns "
        f"and preference evolution.\n"
        f"4. **wildcard_promoted**: List any topics from wildcard (🔍 Explore) papers "
        f"that scored 4+ and deserve promotion to regular interests.\n\n"
        f"Return a JSON object with these four fields. Return ONLY the JSON, no other text."
    )

    data = _parse_json_with_retry(system, user)

    return PreferencesUpdate(
        updated_interests=data["updated_interests"],
        updated_avoid=data["updated_avoid"],
        updated_summary=data["updated_summary"],
        wildcard_promoted=data.get("wildcard_promoted", []),
    )
