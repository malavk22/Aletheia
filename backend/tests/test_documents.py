import io
import uuid
import zipfile

import pytest
from docxs import make_docx
from pdfs import make_pdf, make_scanned_pdf
from sqlalchemy import select

from app.core.config import settings
from app.documents.ocr import ocr_available
from app.models.document import Document, DocumentChunk, DocumentPart
from app.services.documents import (
    backfill_chunks,
    fail_interrupted_documents,
    process_document,
)

PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# A real (tiny) PDF with text, so it passes the upload check and extraction.
PDF_BYTES = make_pdf("Lease agreement")


def zip_bytes(*names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "content")
    return buffer.getvalue()


# A real (tiny) Word file with a heading and text.
DOCX_BYTES = make_docx(("heading", "Summary"), ("p", "Quarterly results."))


def workspace_for(client, email):
    """Sign in as `email` (registering first) and return a new workspace's id."""
    credentials = {"email": email, "password": "correct-horse"}
    client.post("/api/v1/auth/register", json=credentials)
    client.post("/api/v1/auth/login", json=credentials)
    return client.post("/api/v1/workspaces", json={"name": "Contracts"}).json()["id"]


def documents_url(workspace_id):
    return f"/api/v1/workspaces/{workspace_id}/documents"


def upload(client, workspace_id, filename, content):
    return client.post(documents_url(workspace_id), files={"file": (filename, content)})


def processed(client, workspace_id, document_id):
    """The document as it is after background processing.

    The upload answers first and processes afterwards; in tests the background
    job has finished by the time the upload call returns, so reading the
    document again shows the final status."""
    return client.get(document_url(workspace_id, document_id)).json()


def stored_files(upload_dir):
    return [path for path in upload_dir.rglob("*") if path.is_file()]


def test_upload_pdf_is_stored_and_listed(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "lease.pdf", PDF_BYTES)
    listed = client.get(documents_url(workspace_id))

    assert response.status_code == 201
    document = response.json()
    assert document["filename"] == "lease.pdf"
    assert document["content_type"] == PDF_TYPE
    assert document["size_bytes"] == len(PDF_BYTES)
    assert set(document) == {
        "id",
        "filename",
        "content_type",
        "size_bytes",
        "created_at",
        "status",
        "error",
        "part_count",
        "ocr_part_count",
    }
    # The upload answers before the text is extracted.
    assert document["status"] == "processing"
    assert [listed_document["id"] for listed_document in listed.json()] == [document["id"]]
    # Stored under the document's id, inside its workspace's folder.
    stored = upload_dir / workspace_id / document["id"]
    assert stored.read_bytes() == PDF_BYTES


def test_upload_docx(client):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "Report.DOCX", DOCX_BYTES)

    assert response.status_code == 201
    assert response.json()["content_type"] == DOCX_TYPE


def test_upload_rejects_other_file_types(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "notes.txt", b"just some text")

    assert response.status_code == 415
    assert stored_files(upload_dir) == []


def test_upload_rejects_file_that_only_claims_to_be_a_pdf(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "invoice.pdf", b"MZ\x90\x00 not a pdf")

    assert response.status_code == 415
    assert stored_files(upload_dir) == []


def test_upload_rejects_zip_that_only_claims_to_be_a_docx(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "report.docx", zip_bytes("readme.txt"))

    assert response.status_code == 415
    assert stored_files(upload_dir) == []


def test_upload_rejects_empty_file(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "empty.pdf", b"")

    assert response.status_code == 415
    assert stored_files(upload_dir) == []


def test_upload_rejects_file_over_the_size_limit(client, upload_dir, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    workspace_id = workspace_for(client, "ada@example.com")
    too_big = PDF_BYTES + b"0" * (1024 * 1024)

    response = upload(client, workspace_id, "big.pdf", too_big)

    assert response.status_code == 413
    assert stored_files(upload_dir) == []
    assert client.get(documents_url(workspace_id)).json() == []


def test_upload_never_uses_the_filename_as_a_path(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "../../evil.pdf", PDF_BYTES)

    assert response.status_code == 201
    document = response.json()
    assert document["filename"] == "evil.pdf"
    assert stored_files(upload_dir) == [upload_dir / workspace_id / document["id"]]


def test_document_routes_require_login(client):
    url = documents_url(uuid.uuid4())

    assert client.post(url, files={"file": ("lease.pdf", PDF_BYTES)}).status_code == 401
    assert client.get(url).status_code == 401


def test_other_users_cannot_upload_to_or_list_my_workspace(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")
    upload(client, workspace_id, "lease.pdf", PDF_BYTES)

    workspace_for(client, "bob@example.com")  # now signed in as Bob
    uploaded = upload(client, workspace_id, "intruder.pdf", PDF_BYTES)
    listed = client.get(documents_url(workspace_id))

    assert uploaded.status_code == 404
    assert listed.status_code == 404
    # Only Ada's file is on disk.
    assert len(stored_files(upload_dir)) == 1


def document_url(workspace_id, document_id):
    return f"{documents_url(workspace_id)}/{document_id}"


def test_delete_document_removes_row_and_file(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]

    response = client.delete(document_url(workspace_id, document_id))

    assert response.status_code == 204
    assert client.get(documents_url(workspace_id)).json() == []
    assert stored_files(upload_dir) == []


def test_delete_missing_document_is_not_found(client):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]
    client.delete(document_url(workspace_id, document_id))

    deleted_twice = client.delete(document_url(workspace_id, document_id))
    never_existed = client.delete(document_url(workspace_id, uuid.uuid4()))

    assert deleted_twice.status_code == 404
    assert never_existed.status_code == 404


def test_delete_needs_the_document_to_be_in_that_workspace(client, upload_dir):
    contracts = workspace_for(client, "ada@example.com")
    document_id = upload(client, contracts, "lease.pdf", PDF_BYTES).json()["id"]
    minutes = client.post("/api/v1/workspaces", json={"name": "Minutes"}).json()["id"]

    # Ada is a member of both workspaces, but the document lives in Contracts.
    response = client.delete(document_url(minutes, document_id))

    assert response.status_code == 404
    assert len(stored_files(upload_dir)) == 1


def test_other_users_cannot_delete_my_document(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]

    workspace_for(client, "bob@example.com")  # now signed in as Bob
    response = client.delete(document_url(workspace_id, document_id))

    assert response.status_code == 404
    assert len(stored_files(upload_dir)) == 1


def test_delete_requires_login(client):
    response = client.delete(document_url(uuid.uuid4(), uuid.uuid4()))

    assert response.status_code == 401


def parts_url(workspace_id, document_id):
    return f"{document_url(workspace_id, document_id)}/parts"


def test_text_pdf_is_ready_with_its_pages(client):
    workspace_id = workspace_for(client, "ada@example.com")

    uploaded = upload(
        client, workspace_id, "lease.pdf", make_pdf("Clause one.", "Clause two.")
    ).json()
    document = processed(client, workspace_id, uploaded["id"])
    pages = client.get(parts_url(workspace_id, document["id"])).json()

    assert document["status"] == "ready"
    assert document["error"] is None
    assert document["part_count"] == 2
    assert [(page["position"], page["page_number"]) for page in pages] == [(1, 1), (2, 2)]
    assert [page["heading"] for page in pages] == [None, None]
    assert "Clause one." in pages[0]["text"]
    assert "Clause two." in pages[1]["text"]


def test_pdf_without_text_is_kept_but_marked_failed(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "scan.pdf", make_pdf("", ""))
    document = processed(client, workspace_id, response.json()["id"])

    # The upload itself succeeds: the file is kept so it can be processed later.
    assert response.status_code == 201
    assert document["status"] == "failed"
    assert "No text found" in document["error"]
    assert document["part_count"] is None
    assert client.get(parts_url(workspace_id, document["id"])).json() == []
    assert len(stored_files(upload_dir)) == 1


def test_docx_is_ready_with_its_sections(client):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_docx(
        ("p", "Prepared for the board."),
        ("heading", "Revenue"),
        ("p", "Revenue grew 12%."),
        ("heading", "Risks"),
        ("p", "Supplier costs are rising."),
    )

    uploaded = upload(client, workspace_id, "report.docx", content).json()
    document = processed(client, workspace_id, uploaded["id"])
    sections = client.get(parts_url(workspace_id, document["id"])).json()

    assert document["status"] == "ready"
    assert document["part_count"] == 3
    assert [
        (s["position"], s["page_number"], s["heading"], s["text"]) for s in sections
    ] == [
        (1, None, None, "Prepared for the board."),
        (2, None, "Revenue", "Revenue grew 12%."),
        (3, None, "Risks", "Supplier costs are rising."),
    ]


def test_docx_without_text_is_kept_but_marked_failed(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")

    response = upload(client, workspace_id, "blank.docx", make_docx())
    document = processed(client, workspace_id, response.json()["id"])

    assert response.status_code == 201
    assert document["status"] == "failed"
    assert "No text found" in document["error"]
    assert len(stored_files(upload_dir)) == 1


def test_pages_are_deleted_with_their_document(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]
    pages_of_document = select(DocumentPart).where(
        DocumentPart.document_id == uuid.UUID(document_id)
    )
    assert len(db.scalars(pages_of_document).all()) == 1

    client.delete(document_url(workspace_id, document_id))

    assert db.scalars(pages_of_document).all() == []


def test_other_users_cannot_read_my_pages(client):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]

    workspace_for(client, "bob@example.com")  # now signed in as Bob
    response = client.get(parts_url(workspace_id, document_id))

    assert response.status_code == 404


def file_url(workspace_id, document_id):
    return f"{document_url(workspace_id, document_id)}/file"


def test_get_one_document(client):
    workspace_id = workspace_for(client, "ada@example.com")
    uploaded = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()

    response = client.get(document_url(workspace_id, uploaded["id"]))

    assert response.status_code == 200
    assert response.json()["id"] == uploaded["id"]
    assert response.json()["filename"] == "lease.pdf"


def test_original_pdf_opens_in_the_browser(client):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "Lease 2026.pdf", PDF_BYTES).json()["id"]

    response = client.get(file_url(workspace_id, document_id))

    assert response.status_code == 200
    assert response.content == PDF_BYTES
    assert response.headers["content-type"] == PDF_TYPE
    # "inline" asks the browser to display it rather than download it.
    assert response.headers["content-disposition"].startswith("inline")
    assert "Lease%202026.pdf" in response.headers["content-disposition"]
    # Tells the browser not to second-guess the type we decided.
    assert response.headers["x-content-type-options"] == "nosniff"


def test_original_docx_downloads(client):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "report.docx", DOCX_BYTES).json()["id"]

    response = client.get(file_url(workspace_id, document_id))

    assert response.status_code == 200
    assert response.content == DOCX_BYTES
    assert response.headers["content-type"] == DOCX_TYPE
    assert response.headers["content-disposition"].startswith("attachment")


def test_other_users_cannot_get_my_document_or_file(client):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]

    workspace_for(client, "bob@example.com")  # now signed in as Bob

    assert client.get(document_url(workspace_id, document_id)).status_code == 404
    assert client.get(file_url(workspace_id, document_id)).status_code == 404


def test_file_is_only_reachable_through_its_own_workspace(client):
    contracts = workspace_for(client, "ada@example.com")
    document_id = upload(client, contracts, "lease.pdf", PDF_BYTES).json()["id"]
    minutes = client.post("/api/v1/workspaces", json={"name": "Minutes"}).json()["id"]

    response = client.get(file_url(minutes, document_id))

    assert response.status_code == 404


def test_missing_file_on_disk_is_not_found(client, upload_dir):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]
    (upload_dir / workspace_id / document_id).unlink()

    response = client.get(file_url(workspace_id, document_id))

    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}


def test_document_and_file_require_login(client):
    workspace_id, document_id = uuid.uuid4(), uuid.uuid4()

    assert client.get(document_url(workspace_id, document_id)).status_code == 401
    assert client.get(file_url(workspace_id, document_id)).status_code == 401


def test_upload_answers_first_and_processes_in_the_background(client):
    workspace_id = workspace_for(client, "ada@example.com")

    uploaded = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()

    # The answer comes before the text is extracted...
    assert uploaded["status"] == "processing"
    assert uploaded["part_count"] is None
    # ...and the background job finishes the work afterwards.
    document = processed(client, workspace_id, uploaded["id"])
    assert document["status"] == "ready"
    assert document["part_count"] == 1


def test_interrupted_processing_is_marked_failed(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    stuck_id = upload(client, workspace_id, "stuck.pdf", PDF_BYTES).json()["id"]
    done_id = upload(client, workspace_id, "done.pdf", PDF_BYTES).json()["id"]
    # Pretend the server stopped while "stuck.pdf" was being processed.
    db.get(Document, uuid.UUID(stuck_id)).status = "processing"
    db.commit()

    fail_interrupted_documents(db)

    stuck = processed(client, workspace_id, stuck_id)
    assert stuck["status"] == "failed"
    assert "interrupted" in stuck["error"]
    assert processed(client, workspace_id, done_id)["status"] == "ready"


def test_processing_a_document_deleted_in_the_meantime_does_nothing(client):
    # The background job may start after the document was already deleted.
    process_document(uuid.uuid4())  # must not raise


@pytest.mark.skipif(not ocr_available(), reason="Tesseract (OCR) is not installed")
def test_scanned_pdf_is_ready_with_ocr_text(client):
    workspace_id = workspace_for(client, "ada@example.com")
    scan = make_scanned_pdf("Payment is due within thirty days")

    uploaded = upload(client, workspace_id, "scan.pdf", scan).json()
    document = processed(client, workspace_id, uploaded["id"])
    parts = client.get(parts_url(workspace_id, uploaded["id"])).json()

    assert document["status"] == "ready"
    assert document["part_count"] == 1
    assert document["ocr_part_count"] == 1
    assert parts[0]["source"] == "ocr"
    assert "payment" in parts[0]["text"].lower()


def chunks_of(db, document_id):
    return db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == uuid.UUID(document_id))
        .order_by(DocumentChunk.position)
    ).all()


def test_processing_cuts_each_page_into_chunks(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    long_page = " ".join(f"Clause {n} sets out the rent terms." for n in range(1, 61))

    content = make_pdf("Clause one.", long_page)
    document_id = upload(client, workspace_id, "lease.pdf", content).json()["id"]
    chunks = chunks_of(db, document_id)

    # Page 1 is one short chunk; the long page 2 is cut into several, all
    # pointing at page 2, numbered on from page 1.
    assert (chunks[0].position, chunks[0].part_position, chunks[0].text) == (
        1,
        1,
        "Clause one.",
    )
    assert len(chunks) > 2
    assert [chunk.position for chunk in chunks] == list(range(1, len(chunks) + 1))
    assert {chunk.part_position for chunk in chunks[1:]} == {2}
    assert "Clause 60 sets out the rent terms." in chunks[-1].text


def test_docx_sections_are_chunked_separately(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    content = make_docx(
        ("heading", "Revenue"),
        ("p", "Revenue grew 12%."),
        ("heading", "Risks"),
        ("p", "Supplier costs are rising."),
    )

    document_id = upload(client, workspace_id, "report.docx", content).json()["id"]

    assert [(c.part_position, c.text) for c in chunks_of(db, document_id)] == [
        (1, "Revenue grew 12%."),
        (2, "Supplier costs are rising."),
    ]


def test_failed_document_has_no_chunks(client, db):
    workspace_id = workspace_for(client, "ada@example.com")

    document_id = upload(client, workspace_id, "blank.pdf", make_pdf("")).json()["id"]

    assert chunks_of(db, document_id) == []


def test_chunks_are_deleted_with_their_document(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    document_id = upload(client, workspace_id, "lease.pdf", PDF_BYTES).json()["id"]
    assert len(chunks_of(db, document_id)) == 1

    client.delete(document_url(workspace_id, document_id))

    assert chunks_of(db, document_id) == []


def test_every_chunk_is_embedded(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    long_page = " ".join(f"Clause {n} sets out the rent terms." for n in range(1, 61))

    content = make_pdf("Clause one.", long_page)
    document_id = upload(client, workspace_id, "lease.pdf", content).json()["id"]
    chunks = chunks_of(db, document_id)

    assert len(chunks) > 2
    assert all(len(chunk.embedding) == 384 for chunk in chunks)


def test_backfill_chunks_and_embeds_older_documents(client, db):
    workspace_id = workspace_for(client, "ada@example.com")
    first = upload(client, workspace_id, "a.pdf", make_pdf("Clause one.")).json()["id"]
    second = upload(client, workspace_id, "b.pdf", make_pdf("Clause two.")).json()["id"]
    # Make them look like documents processed before V0.3: the first has no
    # chunks at all, the second has a chunk without an embedding.
    for chunk in chunks_of(db, first):
        db.delete(chunk)
    chunks_of(db, second)[0].embedding = None
    db.commit()

    assert backfill_chunks(db) == 2

    assert [c.text for c in chunks_of(db, first)] == ["Clause one."]
    assert all(c.embedding is not None for c in chunks_of(db, first) + chunks_of(db, second))
    # A second run finds nothing left to do.
    assert backfill_chunks(db) == 0
