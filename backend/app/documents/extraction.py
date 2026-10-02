from typing import BinaryIO

import docx
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

# Word's built-in heading styles: what it applies when someone uses its
# heading buttons.
HEADING_STYLES = {"Title"} | {f"Heading {level}" for level in range(1, 10)}


class ExtractionFailed(Exception):
    """Text could not be taken out of a file. str(error) is written for people."""


def clean_text(text: str) -> str:
    # Some PDFs produce the "null" character, which PostgreSQL refuses to store
    # (the whole save would fail). Nothing else is changed: the text is kept as
    # extracted, and tidying it up belongs with chunking (V0.3).
    return text.replace("\x00", "")


def extract_pdf_pages(file: BinaryIO) -> list[str]:
    """Return the text of each page, in order (index 0 is page 1).

    A page with no text is kept as an empty string, so page numbers always
    match the file. Raises ExtractionFailed with a reason people can read.
    """
    try:
        reader = PdfReader(file)
        # Some PDFs are "encrypted" only to restrict printing or copying and
        # open with an empty password; only a real password stops us.
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionFailed("This PDF is password-protected.")
        pages = [clean_text(page.extract_text() or "") for page in reader.pages]
    except ExtractionFailed:
        raise
    except Exception as error:
        # A damaged PDF can make pypdf fail in many different ways; they all
        # mean the same thing to the person who uploaded it.
        raise ExtractionFailed("This PDF could not be read. It may be damaged.") from error

    if not pages:
        raise ExtractionFailed("This PDF has no pages.")
    if not any(text.strip() for text in pages):
        # A scanned PDF is a picture of text: there are pages, but nothing to
        # extract. Reading those needs OCR (a later step).
        raise ExtractionFailed("No text found. This looks like a scanned document.")
    return pages


def extract_docx_sections(file: BinaryIO) -> list[tuple[str | None, str]]:
    """Return (heading, text) for each section of a Word file, in reading order.

    A Word file has no fixed pages (where they break depends on the font, the
    paper and the program), so it is split at its headings instead. Text before
    the first heading has heading None. Tables are included where they appear,
    one line per row with cells separated by " | ".
    Raises ExtractionFailed with a reason people can read.
    """
    try:
        document = docx.Document(file)
        sections: list[tuple[str | None, str]] = []
        heading: str | None = None
        lines: list[str] = []

        def close_section():
            # A heading straight after another heading has no text of its own,
            # so it is not stored as an empty section.
            if lines:
                sections.append((heading, "\n".join(lines)))

        for block in document.iter_inner_content():
            if isinstance(block, Paragraph):
                text = clean_text(block.text).strip()
                if text and _is_heading(block):
                    close_section()
                    heading, lines = text, []
                elif text:
                    lines.append(text)
            else:  # a table
                for row in block.rows:
                    cells = [clean_text(cell.text).strip() for cell in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
        close_section()
    except Exception as error:
        # A damaged file can make python-docx fail in many ways; they all mean
        # the same thing to the person who uploaded it.
        raise ExtractionFailed(
            "This Word file could not be read. It may be damaged."
        ) from error

    if not sections:
        raise ExtractionFailed("No text found in this Word file.")
    return sections


def _is_heading(paragraph: Paragraph) -> bool:
    style = paragraph.style
    return style is not None and style.name in HEADING_STYLES
