import uuid

from pydantic import BaseModel, Field

from app.schemas.search import SearchResult


class AskRequest(BaseModel):
    question: str = Field(max_length=500)
    # Only search these documents; left out, all of the workspace's.
    document_ids: list[uuid.UUID] | None = Field(default=None, max_length=100)


class Citation(SearchResult):
    # The number used in the answer: "[2]" points to the citation with
    # number 2. Only passages the answer cites are returned.
    number: int


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
