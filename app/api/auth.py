"""Authentication endpoints: register, login, logout, me."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.security import create_session_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import UserOut

router = APIRouter()


@router.post("/auth/register", response_model=UserOut)
def register(
    email: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    password: Annotated[str, Form(min_length=12)],
    role: Annotated[str, Form()] = "member",
    db: Session = Depends(get_db),
) -> UserOut:
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    user = User(
        email=email,
        display_name=display_name,
        role=role,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/auth/login")
def login(
    response: Response,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == email))
    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = create_session_token(user.id)
    response.set_cookie(
        get_settings().session_cookie_name,
        token,
        httponly=True,
        samesite="lax",
        secure=get_settings().app_env == "production",
        max_age=get_settings().session_ttl_days * 86400,
    )
    return {"status": "ok"}


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(get_settings().session_cookie_name)
    return {"status": "ok"}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)
