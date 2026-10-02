import io

import pytest
from pdfs import make_encrypted_pdf, make_pdf

from app.documents.extraction import ExtractionFailed, clean_text, extract_pdf_pages


def extract(content: bytes):
    return extract_pdf_pages(io.BytesIO(content))


def test_extracts_text_page_by_page():
    pages = extract(make_pdf("Termination requires notice.", "Payment is due monthly."))

    assert len(pages) == 2
    assert "Termination requires notice." in pages[0]
    assert "Payment is due monthly." in pages[1]


def test_keeps_a_blank_page_in_its_place():
    # Page numbers must stay true to the file, so a blank page is kept (empty)
    # instead of being dropped and shifting every later page number.
    pages = extract(make_pdf("Cover", "", "Clause 3"))

    assert len(pages) == 3
    assert pages[1].strip() == ""
    assert "Clause 3" in pages[2]


def test_pdf_without_any_text_looks_scanned():
    with pytest.raises(ExtractionFailed) as failure:
        extract(make_pdf("", ""))

    assert "scanned" in str(failure.value)


def test_password_protected_pdf_fails_clearly():
    with pytest.raises(ExtractionFailed) as failure:
        extract(make_encrypted_pdf("Secret terms"))

    assert "password" in str(failure.value)


def test_damaged_pdf_fails_clearly():
    with pytest.raises(ExtractionFailed) as failure:
        extract(b"%PDF-1.4\nthis is not really a pdf")

    assert "could not be read" in str(failure.value)


def test_clean_text_removes_null_characters():
    # PostgreSQL refuses to store the null character, and some PDFs produce it.
    assert clean_text("Hello\x00World") == "HelloWorld"
