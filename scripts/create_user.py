# scripts/create_user.py
"""CLI to provision a MediAssist user (admin or clinician).

Usage (from repo root):
    python -m scripts.create_user --email dr@clinic.tz --name "Dr Asha" --role clinician

Prompts for the password (hidden). There is no self-registration: accounts are
created by an administrator on the device.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid

# Make `app` importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.core.security import hash_password  # noqa: E402
from app.db.base import SessionLocal, init_db  # noqa: E402
from app.db.models import User  # noqa: E402


def create_user(db, *, email: str, name: str, password: str, role: str) -> User:
    if role not in ("clinician", "admin"):
        raise ValueError("role must be 'clinician' or 'admin'")
    if db.query(User).filter(User.email == email).first():
        raise ValueError(f"user already exists: {email}")
    user = User(id=f"user-{uuid.uuid4().hex[:8]}", email=email, name=name,
                password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    db.commit()
    return user


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a MediAssist user.")
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--role", default="clinician", choices=["clinician", "admin"])
    args = ap.parse_args()

    password = getpass.getpass("Password: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")

    init_db()
    db = SessionLocal()
    try:
        user = create_user(db, email=args.email, name=args.name,
                           password=password, role=args.role)
        print(f"Created {user.role} {user.email} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
