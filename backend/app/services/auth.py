from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    hash_session_token,
    new_session_token,
    verify_password,
)
from app.models.session import UserSession
from app.models.user import User

SESSION_LIFETIME = timedelta(days=7)


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint on users.email rejected a duplicate.
        db.rollback()
        raise EmailAlreadyRegistered
    return user


def login_user(db: Session, email: str, password: str) -> tuple[User, str]:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentials
    token = new_session_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=datetime.now(timezone.utc) + SESSION_LIFETIME,
        )
    )
    db.commit()
    return user, token


def get_user_for_token(db: Session, token: str) -> User | None:
    return db.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.expires_at > datetime.now(timezone.utc),
        )
    )


def logout_user(db: Session, token: str) -> None:
    db.execute(
        delete(UserSession).where(UserSession.token_hash == hash_session_token(token))
    )
    db.commit()
