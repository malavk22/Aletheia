from typing import BinaryIO

from pypdf import PdfReader


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
