from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.user import User
from app.services.auth import get_user_for_token

SESSION_COOKIE = "session"


def get_current_user(
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    user = get_user_for_token(db, token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
