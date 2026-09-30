import zipfile
from pathlib import PureWindowsPath
from typing import BinaryIO

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# The formats V0.2 can extract text from.
# Planned later, not accepted yet: .txt (text/plain) and .md (text/markdown).
CONTENT_TYPES = {".pdf": PDF, ".docx": DOCX}


class UnsupportedFileType(Exception):
    pass


def display_name(filename: str) -> str:
    # Keep only the last part of whatever name was sent ("../../evil.pdf" ->
    # "evil.pdf"). PureWindowsPath understands both / and \ separators.
    return PureWindowsPath(filename).name


def detect_content_type(filename: str, file: BinaryIO) -> str:
    """Return the file's content type, or raise UnsupportedFileType.

    The extension says what the file claims to be; the contents must agree.
    Neither the name nor the type sent by the browser is trusted on its own.
    """
    content_type = CONTENT_TYPES.get(PureWindowsPath(filename).suffix.lower())
    if content_type is None:
        raise UnsupportedFileType

    file.seek(0)
    looks_right = _is_pdf(file) if content_type == PDF else _is_docx(file)
    file.seek(0)
    if not looks_right:
        raise UnsupportedFileType
    return content_type


def _is_pdf(file: BinaryIO) -> bool:
    # Every PDF starts with these five bytes.
    return file.read(5) == b"%PDF-"


def _is_docx(file: BinaryIO) -> bool:
    # A DOCX is a zip archive that contains word/document.xml. Checking for
    # that file rejects other zips (and spreadsheets) renamed to .docx.
    try:
        with zipfile.ZipFile(file) as archive:
            return "word/document.xml" in archive.namelist()
    except zipfile.BadZipFile:
        return False
