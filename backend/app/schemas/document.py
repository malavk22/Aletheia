import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    # pending | ready | failed
    status: str
    error: str | None
    # Pages for a PDF, sections for a DOCX.
    part_count: int | None
    # How many of those parts were read by OCR (scanned pages).
    ocr_part_count: int | None
    created_at: datetime


class DocumentPartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    # Where the text is: a page number (PDF) or the heading above it (DOCX).
    page_number: int | None
    heading: str | None
    # "text" (taken from the file, exact) or "ocr" (read from an image).
    source: str
    text: str
