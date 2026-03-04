from pydantic import BaseModel


class Paper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    url: str


class FilteredPaper(BaseModel):
    arxiv_id: str
    title: str
    abstract: str
    url: str
    reason: str
    is_wildcard: bool


class PreferencesUpdate(BaseModel):
    updated_interests: list[str]
    updated_avoid: list[str]
    updated_summary: str
    wildcard_promoted: list[str]
