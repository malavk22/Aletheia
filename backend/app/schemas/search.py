import uuid

from pydantic import BaseModel


class SearchResult(BaseModel):
    document_id: uuid.UUID
    filename: str
    # Which chunk of the document (reading order, from 1).
    chunk_position: int
    # Where the text is: a page number (PDF) or the heading above it (DOCX).
    page_number: int | None
    heading: str | None
    # "text" (taken from the file, exact) or "ocr" (read from an image).
    source: str
    text: str
    # How close in meaning to the question: higher is closer (at most 1).
    score: float
