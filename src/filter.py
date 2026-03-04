import logging

from models import Paper, FilteredPaper

logger = logging.getLogger(__name__)


def filter_papers(
    papers: list[Paper],
    preferences: dict,
) -> list[FilteredPaper]:
    """Use Claude to select relevant papers and one wildcard.

    Sends paper abstracts together with the user's preferences to Claude.
    Returns a list of FilteredPaper objects, including up to one wildcard
    from the exploration adjacent categories.
    """
    raise NotImplementedError
