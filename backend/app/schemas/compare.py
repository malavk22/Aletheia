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
