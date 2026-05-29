# backend/app/api/routes/admin.py
"""Admin-only user management API. Every route requires the 'admin' role."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.base import get_db
from app.db.models import User
from app.services import audit, users

router = APIRouter()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: str
    email: str
    name: str
    role: str
    isActive: bool = Field(validation_alias="is_active")
    createdAt: datetime = Field(validation_alias="created_at")


class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str
    role: str


class UpdateUserRequest(BaseModel):
    isActive: bool | None = None
    role: str | None = None


class ResetPasswordRequest(BaseModel):
    password: str


@router.get("/admin/users", response_model=list[UserOut])
def list_all_users(db: Session = Depends(get_db),
                   admin: User = Depends(require_role("admin"))) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in users.list_users(db)]


@router.post("/admin/users", response_model=UserOut)
def create_user_endpoint(req: CreateUserRequest, db: Session = Depends(get_db),
                         admin: User = Depends(require_role("admin"))) -> UserOut:
    try:
        user = users.create_user(db, email=req.email, name=req.name,
                                 password=req.password, role=req.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit.record(db, user_id=admin.id, action="USER_CREATE",
                 target_type="user", target_id=user.id, detail=req.email)
    return UserOut.model_validate(user)


@router.patch("/admin/users/{user_id}", response_model=UserOut)
def update_user_endpoint(user_id: str, req: UpdateUserRequest, db: Session = Depends(get_db),
                         admin: User = Depends(require_role("admin"))) -> UserOut:
    if req.isActive is None and req.role is None:
        raise HTTPException(status_code=400, detail="Nothing to update.")
    if user_id == admin.id and (req.isActive is False or (req.role is not None and req.role != "admin")):
        raise HTTPException(status_code=400,
                            detail="You cannot deactivate or demote your own admin account.")
    try:
        user = users._get(db, user_id)
        if req.isActive is not None:
            user = users.set_active(db, user_id, req.isActive)
        if req.role is not None:
            user = users.set_role(db, user_id, req.role)
    except users.UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit.record(db, user_id=admin.id, action="USER_UPDATE", target_type="user",
                 target_id=user_id, detail=f"isActive={req.isActive} role={req.role}")
    return UserOut.model_validate(user)


@router.post("/admin/users/{user_id}/reset-password")
def reset_password_endpoint(user_id: str, req: ResetPasswordRequest, db: Session = Depends(get_db),
                            admin: User = Depends(require_role("admin"))) -> dict:
    try:
        users.reset_password(db, user_id, req.password)
    except users.UserNotFound:
        raise HTTPException(status_code=404, detail="User not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    audit.record(db, user_id=admin.id, action="USER_RESET_PASSWORD",
                 target_type="user", target_id=user_id)
    return {"ok": True}
