import uuid

from pydantic import BaseModel


class SentenceRead(BaseModel):
    text: str
    # Where the sentence is in its version: its part, and that part's page
    # (PDF) or heading (DOCX).
    part_position: int
    page_number: int | None
    heading: str | None


class ChangeRead(BaseModel):
    # changed (the words changed), formatting (only spacing, capitals or
    # punctuation), removed or added.
    kind: str
    # The sentence in the old version; empty for "added".
    old: SentenceRead | None
    # The sentence in the new version; empty for "removed".
    new: SentenceRead | None


class ChangeCounts(BaseModel):
    changed: int
    formatting: int
    removed: int
    added: int


class ComparisonRead(BaseModel):
    changes: list[ChangeRead]
    counts: ChangeCounts


class ConflictsRequest(BaseModel):
    document_a: uuid.UUID
    document_b: uuid.UUID


class ConflictSide(BaseModel):
    # What this document says, in a few words (Gemini's reading).
    claim: str
    # The document's own words, checked to be in its passage.
    quote: str
    # Where the quote is: its part, and that part's page (PDF) or heading (DOCX).
    part_position: int
    page_number: int | None
    heading: str | None


class ConflictRead(BaseModel):
    # What the two documents disagree about, e.g. "notice period".
    topic: str
    # Why both can't be true (Gemini's reading; the quotes are the evidence).
    explanation: str
    a: ConflictSide
    b: ConflictSide


class ConflictsRead(BaseModel):
    # Potential conflicts: found by AI, each with both quotes checked.
    potential_conflicts: list[ConflictRead]
    # How many passage pairs were checked, and how many conflicts Gemini
    # gave that were dropped because a quote wasn't in its passage.
    checked_pairs: int
    dropped: int
