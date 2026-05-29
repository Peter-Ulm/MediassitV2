# backend/app/db/base.py
"""SQLAlchemy engine, session, declarative base, and the get_db dependency.

The SQLite file lives at <repo-root>/data/mediassist.db regardless of the
process working directory (resolved like main.py resolves CHROMA_PATH).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _resolve_sqlite_url(url: str) -> str:
    """Turn a relative sqlite:///data/x.db into an absolute repo-root path."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    raw = url[len(prefix):]
    p = Path(raw)
    if not p.is_absolute():
        repo_root = Path(__file__).resolve().parents[3]  # backend/app/db -> repo root
        p = repo_root / raw
    p.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{p}"


engine = create_engine(
    _resolve_sqlite_url(settings.DATABASE_URL),
    connect_args={"check_same_thread": False},  # FastAPI uses multiple threads
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create tables if they do not exist. Called at app startup."""
    from app.db import models  # noqa: F401 — register models on Base.metadata
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yield a session, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
