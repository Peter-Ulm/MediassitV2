# backend/app/api/routes/auth.py
"""Auth routes — real DB-backed login issuing a signed JWT."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.security import create_access_token, verify_password
from app.db.base import get_db
from app.db.models import User as UserRow
from app.services import audit

router = APIRouter()


class LoginRequest(BaseModel):
    username: str  # email
    password: str


class User(BaseModel):
    id: str
    name: str
    role: str
    email: str


class LoginResponse(BaseModel):
    token: str
    user: User


@router.post("/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(UserRow).filter(UserRow.email == request.username).first()
    ok = bool(user) and user.is_active and verify_password(request.password, user.password_hash)
    if not ok:
        logger.warning(f"login failed user={request.username}")
        audit.record(db, user_id=(user.id if user else None), action="LOGIN_FAILED", detail=request.username)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, role=user.role)
    audit.record(db, user_id=user.id, action="LOGIN_SUCCESS")
    logger.info(f"login ok user={user.email}")
    return LoginResponse(
        token=token,
        user=User(id=user.id, name=user.name, role=user.role, email=user.email),
    )
