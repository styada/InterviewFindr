"""HTMX page routes (server-rendered HTML)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.security import verify_session_token
from app.db.models import Match, Profile, User
from app.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _current_user_or_redirect(
    request: Request, db: Session
) -> User | RedirectResponse:
    """Resolve the session cookie to a User, or return a 302 to /login."""
    cookie_name = get_settings().session_cookie_name
    token = request.cookies.get(cookie_name)
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    user_id_str = verify_session_token(token)
    if not user_id_str:
        return RedirectResponse(url="/login", status_code=302)
    import uuid

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return RedirectResponse(url="/login", status_code=302)
    user = db.get(User, user_id)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html")


@router.get("/", response_class=HTMLResponse)
def root(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    user = _current_user_or_redirect(request, db)
    if not isinstance(user, User):
        return user  # redirect
    return RedirectResponse(url="/me/matches", status_code=302)


@router.get("/me/profile", response_class=HTMLResponse)
def profile_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    user = _current_user_or_redirect(request, db)
    if not isinstance(user, User):
        return user
    p = db.get(Profile, user.id)
    return templates.TemplateResponse(request, "profile.html", {"profile": p})


@router.get("/me/matches", response_class=HTMLResponse)
def matches_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user = _current_user_or_redirect(request, db)
    if not isinstance(user, User):
        return user
    rows = list(
        db.scalars(
            select(Match)
            .where(Match.user_id == user.id)
            .options(selectinload(Match.job), selectinload(Match.tailored))
            .order_by(Match.match_score.desc())
            .limit(25)
        )
    )
    return templates.TemplateResponse(request, "matches.html", {"matches": rows})


@router.get("/me/matches/{match_id}", response_class=HTMLResponse)
def match_detail_page(
    request: Request,
    match_id: str,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    user = _current_user_or_redirect(request, db)
    if not isinstance(user, User):
        return user
    import uuid

    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        raise HTTPException(404, "match not found")
    m = db.get(
        Match, mid, options=[selectinload(Match.job), selectinload(Match.tailored)]
    )
    if not m or m.user_id != user.id:
        raise HTTPException(404, "match not found")
    return templates.TemplateResponse(
        request, "match_detail.html", {"match": m, "tailored": m.tailored}
    )
