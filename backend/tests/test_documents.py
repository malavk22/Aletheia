import io
import uuid
import zipfile

from app.core.config import settings

PDF_TYPE = "application/pdf"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Only the first bytes matter to the upload check, so these are not full files.
PDF_BYTES = b"%PDF-1.4\n% a tiny stand-in for a real PDF\n"


def zip_bytes(*names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "content")
    return buffer.getvalue()


# A real DOCX is a zip that contains word/document.xml.
DOCX_BYTES = zip_bytes("[Content_Types].xml", "word/document.xml")


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
    assert set(document) == {"id", "filename", "content_type", "size_bytes", "created_at"}
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
