# backend/app/services/users.py
"""Single source of truth for user management (used by the admin API and the CLI)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import User

_ROLES = ("clinician", "admin")


class UserNotFound(Exception):
    """Raised when a user id does not exist."""


def _get(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFound(user_id)
    return user


def create_user(db: Session, *, email: str, name: str, password: str, role: str) -> User:
    if role not in _ROLES:
        raise ValueError(f"role must be one of {_ROLES}")
    if db.query(User).filter(User.email == email).first():
        raise ValueError(f"user already exists: {email}")
    user = User(
        id=f"user-{uuid.uuid4().hex[:8]}",
        email=email, name=name,
        password_hash=hash_password(password),
        role=role, is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.asc()).all()


def set_active(db: Session, user_id: str, is_active: bool) -> User:
    user = _get(db, user_id)
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def set_role(db: Session, user_id: str, role: str) -> User:
    if role not in _ROLES:
        raise ValueError(f"role must be one of {_ROLES}")
    user = _get(db, user_id)
    user.role = role
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, user_id: str, new_password: str) -> User:
    user = _get(db, user_id)
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user
