"""Shared FastAPI dependencies."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_session_token
from app.db.models import User
from app.db.session import get_db


def current_user(
    db: Annotated[Session, Depends(get_db)],
    if_session: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> User:
    """Resolve the current logged-in user from the session cookie."""
    if not if_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    user_id_str = verify_session_token(if_session)
    if not user_id_str:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid session")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user
