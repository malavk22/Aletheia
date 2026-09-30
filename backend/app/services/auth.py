from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


class EmailAlreadyRegistered(Exception):
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
