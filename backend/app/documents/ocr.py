"""OCR: reading text from pictures of pages (scanned documents).

Tesseract is a separate program installed on the machine; pytesseract calls it.
pypdfium2 (built on Chrome's PDF engine) turns a PDF page into an image first.
"""

import shutil
from pathlib import Path

import pypdfium2 as pdfium
import pytesseract

from app.core.config import settings

# PDF sizes are measured in points (1/72 inch). Rendering at 300 dots per inch
# is the usual resolution for OCR: smaller text becomes unreadable, larger is
# slower without reading better.
RENDER_SCALE = 300 / 72
# Where the Windows installer puts it.
WINDOWS_DEFAULT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
LANGUAGE = "eng"
SECONDS_PER_PAGE_LIMIT = 120


def tesseract_path() -> str | None:
    """Where tesseract is, or None if it isn't installed."""
    if settings.tesseract_cmd:
        return settings.tesseract_cmd
    found = shutil.which("tesseract")
    if found:
        return found
    return str(WINDOWS_DEFAULT) if WINDOWS_DEFAULT.is_file() else None


def ocr_available() -> bool:
    return tesseract_path() is not None


def ocr_pdf_page(pdf: pdfium.PdfDocument, index: int) -> str:
    """Render one page (index 0 is page 1) as an image and read its text."""
    pytesseract.pytesseract.tesseract_cmd = tesseract_path()
    image = pdf[index].render(scale=RENDER_SCALE).to_pil()
    return pytesseract.image_to_string(
        image, lang=LANGUAGE, timeout=SECONDS_PER_PAGE_LIMIT
    )
