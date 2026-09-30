import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.session import UserSession
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


LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"
CREDENTIALS = {"email": "ada@example.com", "password": "correct-horse"}


def register_and_login(client):
    client.post(REGISTER_URL, json=CREDENTIALS)
    return client.post(LOGIN_URL, json=CREDENTIALS)


def session_of_test_user(db):
    # Looks the session up by its user, so rows that already exist in the
    # database (real accounts) are never picked by mistake.
    return db.scalar(
        select(UserSession)
        .join(User, User.id == UserSession.user_id)
        .where(User.email == CREDENTIALS["email"])
    )


def test_login_sets_httponly_cookie(client):
    response = register_and_login(client)

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith("session=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_login_accepts_email_in_any_case(client):
    client.post(REGISTER_URL, json=CREDENTIALS)

    response = client.post(
        LOGIN_URL, json={"email": "ADA@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 200


def test_login_rejects_wrong_password_and_unknown_email_the_same_way(client):
    client.post(REGISTER_URL, json=CREDENTIALS)

    wrong_password = client.post(
        LOGIN_URL, json={"email": "ada@example.com", "password": "wrong-password"}
    )
    unknown_email = client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": "correct-horse"}
    )

    assert wrong_password.status_code == 401
    assert unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert "set-cookie" not in wrong_password.headers


def test_me_returns_logged_in_user(client):
    register_and_login(client)

    response = client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_me_requires_login(client):
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_logout_makes_old_cookie_useless(client):
    register_and_login(client)
    token = client.cookies["session"]

    response = client.post(LOGOUT_URL)
    client.cookies.set("session", token)

    assert response.status_code == 204
    assert client.get(ME_URL).status_code == 401


def test_logout_without_cookie_is_harmless(client):
    response = client.post(LOGOUT_URL)

    assert response.status_code == 204


def test_expired_session_is_rejected(client, db):
    register_and_login(client)
    session = session_of_test_user(db)
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()

    response = client.get(ME_URL)

    assert response.status_code == 401


def test_session_token_is_stored_hashed(client, db):
    register_and_login(client)
    token = client.cookies["session"]

    session = session_of_test_user(db)

    assert session.token_hash != token
    assert session.token_hash == hashlib.sha256(token.encode()).hexdigest()
