"""Builds small but real PDF files for tests, with known text on each page."""

import io

from pypdf import PdfReader, PdfWriter


def _escape(text: str) -> str:
    # Inside a PDF text string, backslash and parentheses must be escaped.
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(*page_texts: str) -> bytes:
    """One page per argument. An empty string makes a page with no text,
    which is what a scanned page looks like to a text extractor."""
    page_ids = [4 + 2 * index for index in range(len(page_texts))]
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: (
            f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] "
            f"/Count {len(page_ids)} >>"
        ).encode(),
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    for page_id, text in zip(page_ids, page_texts):
        content_id = page_id + 1
        stream = f"BT /F1 12 Tf 72 720 Td ({_escape(text)}) Tj ET".encode() if text else b""
        objects[content_id] = (
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"
        )
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()

    # Write the objects, then the cross-reference table that says where each
    # one starts (byte offsets), which every PDF reader relies on.
    output = b"%PDF-1.4\n"
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(output)
        output += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref_start = len(output)
    size = max(objects) + 1
    output += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for number in range(1, size):
        output += f"{offsets[number]:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode()
    return output


def make_encrypted_pdf(*page_texts: str) -> bytes:
    """The same PDF, locked with a password."""
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(make_pdf(*page_texts))))
    writer.encrypt(user_password="secret", owner_password="secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
