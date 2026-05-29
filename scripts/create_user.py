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

# Make `app` importable when run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app.db.base import SessionLocal, init_db  # noqa: E402
from app.services.users import create_user  # noqa: E402


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
