from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.user import UserCreate, UserRead
from app.services.auth import EmailAlreadyRegistered, register_user

router = APIRouter(prefix="/auth")


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    try:
        return register_user(db, data.email, data.password)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=409, detail="Email already registered")
