# scripts/seed_demo.py
"""Idempotently seed the demo doctor account.

The login page has a "Continue as Demo Doctor" button (and shows demo
credentials) for quick access during demos. This script ensures that account
actually exists in the local database so the button works out of the box on a
fresh clone.

DEMO CONVENIENCE ONLY. The app self-identifies as a demo environment; before any
real deployment, remove this seed (and change/disable the demo account). Real
accounts are created with scripts/create_user.py — there is no self-registration.

Run from the repo root:
    python -m scripts.seed_demo
"""

from __future__ import annotations

import os
import sys

# Make `app` importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.db.base import SessionLocal, init_db  # noqa: E402
from app.db.models import User  # noqa: E402
from app.services.users import create_user  # noqa: E402

DEMO_EMAIL = "dr.demo@mediassist.test"
DEMO_PASSWORD = "DemoPass123"
DEMO_ADMIN_EMAIL = "admin.demo@mediassist.test"
DEMO_ADMIN_PASSWORD = "DemoPass123"


def _seed_one(db, email, name, password, role):
    if db.query(User).filter(User.email == email).first():
        print(f"Demo account already exists: {email}")
        return
    create_user(db, email=email, name=name, password=password, role=role)
    print(f"Seeded demo account: {email} / {password}  ({role})")


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        _seed_one(db, DEMO_EMAIL, "Dr Demo", DEMO_PASSWORD, "clinician")
        _seed_one(db, DEMO_ADMIN_EMAIL, "Admin Demo", DEMO_ADMIN_PASSWORD, "admin")
    finally:
        db.close()


if __name__ == "__main__":
    main()
