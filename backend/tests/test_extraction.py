import io
import zipfile

import pytest
from docxs import make_docx
from pdfs import join_pdfs, make_encrypted_pdf, make_pdf, make_scanned_pdf

from app.documents import extraction
from app.documents.ocr import ocr_available
from app.documents.extraction import (
    ExtractionFailed,
    clean_text,
    extract_docx_sections,
    extract_pdf_pages,
)


def extract(content: bytes):
    return extract_pdf_pages(io.BytesIO(content))


needs_tesseract = pytest.mark.skipif(
    not ocr_available(), reason="Tesseract (OCR) is not installed on this machine"
)


def test_extracts_text_page_by_page():
    pages = extract(make_pdf("Termination requires notice.", "Payment is due monthly."))

    assert len(pages) == 2
    assert "Termination requires notice." in pages[0][0]
    assert "Payment is due monthly." in pages[1][0]
    # Taken from the PDF's own text layer, not OCR.
    assert [source for _, source in pages] == ["text", "text"]


def test_keeps_a_blank_page_in_its_place():
    # Page numbers must stay true to the file, so a blank page is kept (empty)
    # instead of being dropped and shifting every later page number.
    pages = extract(make_pdf("Cover", "", "Clause 3"))

    assert len(pages) == 3
    assert pages[1][0].strip() == ""
    assert "Clause 3" in pages[2][0]


def test_scanned_pdf_without_ocr_says_so(monkeypatch):
    monkeypatch.setattr(extraction, "ocr_available", lambda: False)

    with pytest.raises(ExtractionFailed) as failure:
        extract(make_scanned_pdf("Termination requires notice"))

    assert "scanned" in str(failure.value)
    assert "OCR is not available" in str(failure.value)


@needs_tesseract
def test_scanned_page_is_read_with_ocr():
    pages = extract(make_scanned_pdf("Termination requires thirty days notice"))

    assert len(pages) == 1
    text, source = pages[0]
    assert source == "ocr"
    # OCR can misread a letter here and there, so check the words, not the
    # exact string.
    words = text.lower().split()
    assert {"termination", "requires", "thirty", "days", "notice"} <= set(words)


@needs_tesseract
def test_only_pages_without_text_go_through_ocr():
    pdf = join_pdfs(make_pdf("Cover page"), make_scanned_pdf("Signed by both parties"))

    pages = extract(pdf)

    assert [source for _, source in pages] == ["text", "ocr"]
    assert "Cover page" in pages[0][0]
    assert "signed" in pages[1][0].lower()


@needs_tesseract
def test_blank_pdf_finds_nothing_even_with_ocr():
    with pytest.raises(ExtractionFailed) as failure:
        extract(make_pdf("", ""))

    assert "even after reading the pages as images" in str(failure.value)


def test_ocr_failure_fails_clearly(monkeypatch):
    def broken_ocr(pdf, index):
        raise RuntimeError("tesseract crashed")

    monkeypatch.setattr(extraction, "ocr_available", lambda: True)
    monkeypatch.setattr(extraction, "ocr_pdf_page", broken_ocr)

    with pytest.raises(ExtractionFailed) as failure:
        extract(make_scanned_pdf("Anything"))

    assert "OCR failed" in str(failure.value)


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


def sections_of(content: bytes):
    return extract_docx_sections(io.BytesIO(content))


def test_docx_is_split_into_sections_at_headings():
    sections = sections_of(
        make_docx(
            ("p", "Agreement between Acme and Beta."),
            ("heading", "Payment terms"),
            ("p", "Payment is due monthly."),
            ("p", "Late payments incur a fee."),
            ("heading", "Termination"),
            ("p", "Either party may end this agreement."),
        )
    )

    assert sections == [
        (None, "Agreement between Acme and Beta."),
        ("Payment terms", "Payment is due monthly.\nLate payments incur a fee."),
        ("Termination", "Either party may end this agreement."),
    ]


def test_docx_tables_are_kept_in_reading_order():
    sections = sections_of(
        make_docx(
            ("heading", "Prices"),
            ("p", "The prices are:"),
            ("table", [["Item", "Price"], ["Licence", "100"]]),
            ("p", "Prices exclude tax."),
        )
    )

    assert sections == [
        ("Prices", "The prices are:\nItem | Price\nLicence | 100\nPrices exclude tax."),
    ]


def test_docx_heading_without_text_is_not_stored_on_its_own():
    sections = sections_of(
        make_docx(("heading", "Chapter 1"), ("heading", "Scope"), ("p", "This covers everything."))
    )

    assert sections == [("Scope", "This covers everything.")]


def test_docx_without_headings_is_one_section():
    sections = sections_of(make_docx(("p", "First line."), ("p", "Second line.")))

    assert sections == [(None, "First line.\nSecond line.")]


def test_empty_docx_fails_clearly():
    with pytest.raises(ExtractionFailed) as failure:
        sections_of(make_docx())

    assert "No text found" in str(failure.value)


def test_damaged_docx_fails_clearly():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "not xml")
        archive.writestr("word/document.xml", "not xml either")

    with pytest.raises(ExtractionFailed) as failure:
        sections_of(buffer.getvalue())

    assert "could not be read" in str(failure.value)
