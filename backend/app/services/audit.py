# backend/app/services/audit.py
"""Append-only audit logging. Never raises into the request path."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logger import logger
from app.db.models import AuditLog


def record(db: Session, *, user_id: str | None, action: str,
           target_type: str | None = None, target_id: str | None = None,
           detail: str | None = None) -> None:
    try:
        db.add(AuditLog(user_id=user_id, action=action, target_type=target_type,
                        target_id=target_id, detail=detail))
        db.commit()
    except Exception as exc:  # availability of care > audit completeness, but log the gap
        logger.warning(f"audit write failed action={action}: {exc}")
        db.rollback()
