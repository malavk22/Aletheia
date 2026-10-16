from datetime import datetime

from pydantic import BaseModel


class FactRead(BaseModel):
    # The order the facts were extracted in, from 1.
    position: int
    # person, organization, date, amount or requirement.
    kind: str
    value: str
    # Dates only: YYYY-MM-DD, when the document gives a full date.
    normalized: str | None
    about: str | None
    # The document's own words the fact comes from.
    quote: str
    # Where the quote is: its part, and that part's page (PDF) or heading (DOCX).
    part_position: int
    page_number: int | None
    heading: str | None
    # "text" (taken from the file, exact) or "ocr" (read from an image).
    source: str


class FactsRead(BaseModel):
    # When facts were last extracted; empty if never.
    extracted_at: datetime | None
    facts: list[FactRead]
    # After an extraction only: how many facts Gemini gave that were dropped
    # because their evidence didn't check out.
    dropped: int | None = None
