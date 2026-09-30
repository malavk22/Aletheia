import uuid

from sqlalchemy import select

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
