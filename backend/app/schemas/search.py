import uuid

from pydantic import BaseModel


class SearchResult(BaseModel):
    document_id: uuid.UUID
    filename: str
    # Which chunk of the document (reading order, from 1).
    chunk_position: int
    # Which page or section of the document (reading order, from 1).
    part_position: int
    # Where the text is: a page number (PDF) or the heading above it (DOCX).
    page_number: int | None
    heading: str | None
    # "text" (taken from the file, exact) or "ocr" (read from an image).
    source: str
    text: str
    # Higher is a better match. Semantic: closeness in meaning (at most 1).
    # Keyword: how often and how close together the words appear. The two
    # are on different scales and should not be compared.
    score: float
