from pydantic import BaseModel, Field

from app.schemas.search import SearchResult


class AskRequest(BaseModel):
    question: str = Field(max_length=500)


class Citation(SearchResult):
    # The number used in the answer: "[2]" points to the citation with
    # number 2. Only passages the answer cites are returned.
    number: int


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
