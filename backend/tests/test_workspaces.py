import uuid

from sqlalchemy import select

from app.models.document import Document
from app.models.user import User
from app.models.workspace import WorkspaceMembership

WORKSPACES_URL = "/api/v1/workspaces"


def login_as(client, email):
    credentials = {"email": email, "password": "correct-horse"}
    client.post("/api/v1/auth/register", json=credentials)
    client.post("/api/v1/auth/login", json=credentials)


def test_create_workspace_appears_in_my_list(client):
    login_as(client, "ada@example.com")

    created = client.post(WORKSPACES_URL, json={"name": "Contracts"})
    listed = client.get(WORKSPACES_URL)

    assert created.status_code == 201
    assert created.json()["name"] == "Contracts"
    assert listed.json() == [created.json()]


def test_creator_becomes_owner(client, db):
    login_as(client, "ada@example.com")

    workspace_id = client.post(WORKSPACES_URL, json={"name": "Contracts"}).json()["id"]

    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == uuid.UUID(workspace_id)
        )
    )
    assert membership.role == "owner"


def test_get_my_workspace(client):
    login_as(client, "ada@example.com")
    created = client.post(WORKSPACES_URL, json={"name": "Contracts"}).json()

    response = client.get(f"{WORKSPACES_URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_workspace_routes_require_login(client):
    assert client.post(WORKSPACES_URL, json={"name": "Contracts"}).status_code == 401
    assert client.get(WORKSPACES_URL).status_code == 401
    assert client.get(f"{WORKSPACES_URL}/{uuid.uuid4()}").status_code == 401


def test_other_users_cannot_see_my_workspace(client):
    login_as(client, "ada@example.com")
    workspace_id = client.post(WORKSPACES_URL, json={"name": "Contracts"}).json()["id"]

    login_as(client, "bob@example.com")
    listed = client.get(WORKSPACES_URL)
    not_mine = client.get(f"{WORKSPACES_URL}/{workspace_id}")
    missing = client.get(f"{WORKSPACES_URL}/{uuid.uuid4()}")

    assert listed.json() == []
    assert not_mine.status_code == 404
    # Same answer as a workspace that does not exist, so nothing is revealed.
    assert not_mine.json() == missing.json()


def test_create_workspace_rejects_blank_name(client):
    login_as(client, "ada@example.com")

    response = client.post(WORKSPACES_URL, json={"name": "   "})

    assert response.status_code == 422


PDF_BYTES = b"%PDF-1.4\n% a tiny stand-in for a real PDF\n"


def create_with_document(client, upload_dir):
    """Create a workspace holding one uploaded PDF; return the workspace id."""
    workspace_id = client.post(WORKSPACES_URL, json={"name": "Contracts"}).json()["id"]
    client.post(
        f"{WORKSPACES_URL}/{workspace_id}/documents",
        files={"file": ("lease.pdf", PDF_BYTES)},
    )
    assert (upload_dir / workspace_id).is_dir()
    return workspace_id


def documents_in(db, workspace_id):
    return db.scalars(
        select(Document).where(Document.workspace_id == uuid.UUID(workspace_id))
    ).all()


def test_owner_can_delete_workspace_with_everything_in_it(client, db, upload_dir):
    login_as(client, "ada@example.com")
    workspace_id = create_with_document(client, upload_dir)

    response = client.delete(f"{WORKSPACES_URL}/{workspace_id}")

    assert response.status_code == 204
    assert client.get(WORKSPACES_URL).json() == []
    assert client.get(f"{WORKSPACES_URL}/{workspace_id}").status_code == 404
    assert documents_in(db, workspace_id) == []
    assert not (upload_dir / workspace_id).exists()


def test_other_users_cannot_delete_my_workspace(client, db, upload_dir):
    login_as(client, "ada@example.com")
    workspace_id = create_with_document(client, upload_dir)

    login_as(client, "bob@example.com")
    response = client.delete(f"{WORKSPACES_URL}/{workspace_id}")

    assert response.status_code == 404
    assert len(documents_in(db, workspace_id)) == 1
    assert (upload_dir / workspace_id).is_dir()


def test_members_who_are_not_the_owner_cannot_delete(client, db, upload_dir):
    login_as(client, "ada@example.com")
    workspace_id = create_with_document(client, upload_dir)
    # Sharing does not exist yet, so add Bob as a non-owner member directly.
    login_as(client, "bob@example.com")
    bob = db.scalar(select(User).where(User.email == "bob@example.com"))
    db.add(
        WorkspaceMembership(
            user_id=bob.id, workspace_id=uuid.UUID(workspace_id), role="viewer"
        )
    )
    db.commit()

    can_see = client.get(f"{WORKSPACES_URL}/{workspace_id}")
    response = client.delete(f"{WORKSPACES_URL}/{workspace_id}")

    assert can_see.status_code == 200
    assert response.status_code == 403
    assert len(documents_in(db, workspace_id)) == 1
    assert (upload_dir / workspace_id).is_dir()


def test_delete_workspace_twice_is_not_found(client):
    login_as(client, "ada@example.com")
    workspace_id = client.post(WORKSPACES_URL, json={"name": "Contracts"}).json()["id"]
    client.delete(f"{WORKSPACES_URL}/{workspace_id}")

    response = client.delete(f"{WORKSPACES_URL}/{workspace_id}")

    assert response.status_code == 404


def test_delete_workspace_requires_login(client):
    response = client.delete(f"{WORKSPACES_URL}/{uuid.uuid4()}")

    assert response.status_code == 401
