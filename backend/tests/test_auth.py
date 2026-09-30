from sqlalchemy import select

from app.models.user import User

REGISTER_URL = "/api/v1/auth/register"


def test_register_creates_user(client):
    response = client.post(
        REGISTER_URL, json={"email": "ada@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert set(body) == {"id", "email"}


def test_register_stores_password_as_argon2_hash(client, db):
    client.post(
        REGISTER_URL, json={"email": "ada@example.com", "password": "correct-horse"}
    )

    user = db.scalar(select(User).where(User.email == "ada@example.com"))
    assert user.password_hash != "correct-horse"
    assert user.password_hash.startswith("$argon2")


def test_register_treats_email_as_case_insensitive(client):
    first = client.post(
        REGISTER_URL, json={"email": "Ada@Example.com", "password": "correct-horse"}
    )
    second = client.post(
        REGISTER_URL, json={"email": "ada@example.com", "password": "other-password"}
    )

    assert first.json()["email"] == "ada@example.com"
    assert second.status_code == 409


def test_register_rejects_short_password(client):
    response = client.post(
        REGISTER_URL, json={"email": "ada@example.com", "password": "short"}
    )

    assert response.status_code == 422


def test_register_rejects_invalid_email(client):
    response = client.post(
        REGISTER_URL, json={"email": "not-an-email", "password": "correct-horse"}
    )

    assert response.status_code == 422
