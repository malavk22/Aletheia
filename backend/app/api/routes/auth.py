from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserRead
from app.services.auth import (
    SESSION_LIFETIME,
    EmailAlreadyRegistered,
    InvalidCredentials,
    login_user,
    logout_user,
    register_user,
)

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        return register_user(db, data.email, data.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=409, detail="Email already registered")


@router.post("/login", response_model=UserRead)
def login(data: UserLogin, response: Response, db: Session = Depends(get_db)):
    try:
        user, token = login_user(db, data.email, data.password)
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return user


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    token: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: Session = Depends(get_db),
):
    if token:
        logout_user(db, token)
    response.delete_cookie(SESSION_COOKIE)
