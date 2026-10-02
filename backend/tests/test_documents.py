import io
import uuid
import zipfile

from docxs import make_docx
from pdfs import make_pdf
from sqlalchemy import select

from app.core.config import settings
from app.models.document import DocumentPart

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
    }
    assert listed.json() == [document]
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

    document = upload(
        client, workspace_id, "lease.pdf", make_pdf("Clause one.", "Clause two.")
    ).json()
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
    document = response.json()

    # The upload itself succeeds: the file is kept so it can be processed later.
    assert response.status_code == 201
    assert document["status"] == "failed"
    assert "scanned" in document["error"]
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

    document = upload(client, workspace_id, "report.docx", content).json()
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
    document = response.json()

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
