"""Session-based auth for the three roles: resident, tow operator, board.

No shared user-accounts table - each role has its own simple check, mirroring
the small-trusted-group pattern used by wholesale-crm's single-admin login:
  - resident: unit (address) + 6-digit PIN, hashed with bcrypt.
  - tow operator: one shared company code (env TOW_COMPANY_CODE).
  - board/PMG: one shared admin username+password (env ADMIN_USERNAME/PASSWORD).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import Config
from app.database import get_db
from app.models import Unit

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_pin(pin: str) -> str:
    return pwd_context.hash(pin)


def verify_pin(pin: str, pin_hash: str) -> bool:
    return pwd_context.verify(pin, pin_hash)


def _redirect(location: str) -> HTTPException:
    return HTTPException(status_code=303, headers={"Location": location})


# ------------------------------------------------------------- resident ---

def get_current_resident(request: Request, db: Session = Depends(get_db)) -> Unit | None:
    unit_id = request.session.get("resident_unit_id")
    if not unit_id:
        return None
    return db.query(Unit).filter(Unit.id == unit_id).first()


def require_resident(request: Request, db: Session = Depends(get_db)) -> Unit:
    unit = get_current_resident(request, db)
    if not unit:
        raise _redirect("/resident/login")
    return unit


# ---------------------------------------------------------- tow operator --

def is_tow_operator(request: Request) -> bool:
    return bool(request.session.get("tow_operator"))


def require_tow_operator(request: Request) -> None:
    if not is_tow_operator(request):
        raise _redirect("/tow/login")


# ------------------------------------------------------------------ board -

def get_current_board_user(request: Request) -> str | None:
    return request.session.get("board_user")


def require_board(request: Request) -> str:
    user = get_current_board_user(request)
    if not user:
        raise _redirect("/board/login")
    return user


def authenticate_board(username: str, password: str) -> bool:
    return username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD
