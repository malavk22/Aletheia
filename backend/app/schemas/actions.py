import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ActionRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    # deadline or task.
    kind: str
    title: str
    # Who has to do it, as the document says; empty if not said.
    responsible: str | None
    # What the document says about when: exact (a full date), relative
    # ("within 30 days of leaving", a date without a year) or none.
    due_kind: str
    # The "when" in the document's own words.
    due_text: str | None
    due_date: date | None
    # Where the date came from: "document" (exact only) or "person".
    due_date_source: str | None
    # The document's own words, checked to be on the page.
    quote: str
    # high, medium or low, worked out by rules from the evidence.
    confidence: str
    # suggested (not yet counted), confirmed or dismissed.
    status: str
    confirmed_at: datetime | None
    # Where the quote is: its part, and that part's page (PDF) or heading
    # (DOCX); "ocr" if the text was read from an image.
    part_position: int
    page_number: int | None
    heading: str | None
    source: str


class DocumentActionsRead(BaseModel):
    # When actions were last extracted; empty if never.
    extracted_at: datetime | None
    actions: list[ActionRead]
    # After an extraction only: how many actions Gemini gave that were
    # dropped because their evidence didn't check out.
    dropped: int | None = None


class ActionUpdate(BaseModel):
    """A person's decision. Only the fields sent are changed."""

    status: Literal["suggested", "confirmed", "dismissed"] | None = None
    title: str | None = Field(default=None, max_length=300)
    # A date the person sets (saved as theirs), or null to clear it.
    due_date: date | None = None
