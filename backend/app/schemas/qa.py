import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.search import SearchResult


class AskRequest(BaseModel):
    question: str = Field(max_length=500)
    # Only search these documents; left out, all of the workspace's.
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)
    # With one document chosen: only these of its pages or sections (part
    # positions, both included); left out, all of them.
    part_from: int | None = None
    part_to: int | None = None


class Citation(SearchResult):
    # The number used in the answer: "[2]" points to the citation with
    # number 2. Only passages the answer cites are returned.
    number: int


class UnsupportedSentence(BaseModel):
    # A sentence of the answer, exactly as written in it.
    sentence: str
    # no_source: it cites nothing; number_not_in_source: it has numbers
    # (listed, as written) that the passages it cites don't contain.
    reason: Literal["no_source", "number_not_in_source"]
    numbers: list[str]


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    # The answer's sentences its sources don't back (V0.9); empty if none.
    unsupported: list[UnsupportedSentence]
