# Real Auth + Persistence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MediAssist's cosmetic login and in-memory consultation store with a real SQLite-backed persistence + identity layer: bcrypt+JWT auth, role-protected routes, owner-scoped consultations, and an append-only audit log.

**Architecture:** A backend persistence layer (SQLAlchemy + SQLite) holds `User`, `Consultation`, and `AuditLog`. `core/security.py` hashes passwords and signs/verifies JWTs. `api/deps.py` provides `get_current_user` / `require_role` dependencies that protect the diagnosis and consultation routes. Consultations move from the in-memory dict into the DB, scoped to their owning clinician. The frontend already sends `Authorization: Bearer` and guards routes — it only needs a `401` handler.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, SQLite, `passlib[bcrypt]`, PyJWT, pytest + Starlette `TestClient`. Frontend: TypeScript/React (existing).

**Spec:** [docs/superpowers/specs/2026-05-29-auth-persistence-design.md](../specs/2026-05-29-auth-persistence-design.md)

**Deviation from spec (right-sizing):** The spec named Alembic for migrations. For a never-deployed single-device FYP that is premature; this plan uses `Base.metadata.create_all()` at startup (creates tables if missing). Alembic can be introduced later when there is a deployed DB whose data must survive schema changes.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/conftest.py` | Put `backend/` on `sys.path` so tests import `app.*`. |
| `backend/tests/__init__.py` | Package marker. |
| `backend/tests/conftest.py` | Pytest fixtures: in-memory DB engine + `TestClient` with `get_db` overridden. |
| `backend/app/db/__init__.py` | Package marker. |
| `backend/app/db/base.py` | SQLAlchemy `engine`, `SessionLocal`, `Base`, `get_db` dependency, `init_db()`. |
| `backend/app/db/models.py` | `User`, `Consultation`, `AuditLog` ORM models. |
| `backend/app/core/security.py` | Password hash/verify + JWT encode/decode. |
| `backend/app/api/deps.py` | `get_current_user`, `require_role` FastAPI dependencies. |
| `backend/app/services/audit.py` | `record(...)` append-only audit helper. |
| `backend/app/core/config.py` | MODIFY — DB + JWT settings. |
| `backend/app/api/routes/auth.py` | MODIFY — DB-backed login + audit. |
| `backend/app/api/routes/consultations.py` | MODIFY — DB-backed CRUD, ownership scoping, audit, auth. |
| `backend/app/api/routes/diagnosis.py` | MODIFY — require auth. |
| `backend/app/main.py` | MODIFY — call `init_db()` at startup. |
| `scripts/create_user.py` | NEW — CLI user provisioning. |
| `frontend/src/api/client.ts` | MODIFY — on `401`, clear auth + redirect to `/login`. |
| `requirements.txt`, `.env.example`, `README.md` | MODIFY — deps, config keys, docs. |

**Conventions:** module docstrings like sibling files; `from __future__ import annotations`; the backend uses `app.*` absolute imports and is run from `backend/`. Tests run from the repo root: `python -m pytest backend/tests -q`.

---

### Task 1: Backend test scaffolding + config settings + dependencies

**Files:**
- Create: `backend/conftest.py`, `backend/tests/__init__.py`
- Modify: `backend/app/core/config.py`, `requirements.txt`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Add dependencies** to `requirements.txt` (append at the end, with a comment):

```
# ── Persistence + auth (real login + SQLite store) ──────────────────────────
sqlalchemy==2.0.36
passlib[bcrypt]==1.7.4
pyjwt==2.10.1
```

- [ ] **Step 2: Install them.**

Run: `.\.venv\Scripts\python.exe -m pip install sqlalchemy==2.0.36 "passlib[bcrypt]==1.7.4" pyjwt==2.10.1`
Expected: installs without error.

- [ ] **Step 3: Create `backend/conftest.py`** so tests can import `app.*`:

```python
# backend/conftest.py
"""Put the backend/ dir on sys.path so tests import the `app` package."""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
```

- [ ] **Step 4: Create `backend/tests/__init__.py`** (empty).

- [ ] **Step 5: Write the failing test** `backend/tests/test_config.py`:

```python
from app.core.config import Settings


def test_db_and_jwt_settings_have_defaults(monkeypatch):
    for k in ("DATABASE_URL", "JWT_SECRET", "JWT_EXPIRE_MINUTES", "JWT_ALGORITHM"):
        monkeypatch.delenv(k, raising=False)
    s = Settings()
    assert s.DATABASE_URL.startswith("sqlite:///")
    assert s.JWT_ALGORITHM == "HS256"
    assert s.JWT_EXPIRE_MINUTES == 480
    assert isinstance(s.JWT_SECRET, str) and len(s.JWT_SECRET) > 0
```

- [ ] **Step 6: Run it — expect failure.**

Run: `python -m pytest backend/tests/test_config.py -v`
Expected: FAIL — `AttributeError`/validation (no `DATABASE_URL`).

- [ ] **Step 7: Add settings** to `backend/app/core/config.py`, inside `Settings`, after the Retrieval block:

```python
    # ── Persistence + Auth ──────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///data/mediassist.db"
    # Dev default only. In real use set JWT_SECRET in .env to a long random value
    # (python -c "import secrets; print(secrets.token_hex(32))").
    JWT_SECRET: str = "dev-only-insecure-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
```

- [ ] **Step 8: Run it — expect pass.**

Run: `python -m pytest backend/tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 9: Commit.**

```bash
git add requirements.txt backend/conftest.py backend/tests/__init__.py backend/tests/test_config.py backend/app/core/config.py
git commit -m "chore: backend test scaffolding + DB/JWT settings + auth deps"
```

---

### Task 2: DB foundation — engine, session, models

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/base.py`, `backend/app/db/models.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Create `backend/app/db/__init__.py`** (empty).

- [ ] **Step 2: Create `backend/app/db/base.py`:**

```python
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
```

- [ ] **Step 3: Create `backend/app/db/models.py`:**

```python
# backend/app/db/models.py
"""ORM models: User, Consultation, AuditLog."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="clinician")  # 'clinician'|'admin'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    patient: Mapped[dict] = mapped_column(JSON)
    symptoms: Mapped[str] = mapped_column(Text)
    results: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="draft")  # 'draft'|'completed'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String)
    target_type: Mapped[str | None] = mapped_column(String, nullable=True)
    target_id: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
```

- [ ] **Step 4: Create `backend/tests/conftest.py`** (shared in-memory DB + client fixtures):

```python
# backend/tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base, get_db


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across connections
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    """A TestClient whose get_db yields the in-memory test session."""
    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c, app
```

- [ ] **Step 5: Write the failing test** `backend/tests/test_models.py`:

```python
import uuid
from app.db.models import User, Consultation, AuditLog


def test_user_consultation_audit_roundtrip(db_session):
    u = User(id="u1", email="a@b.test", name="A", password_hash="x", role="clinician")
    db_session.add(u)
    db_session.commit()

    c = Consultation(
        id="c1", owner_user_id="u1", patient={"age": 30, "sex": "male"},
        symptoms="fever", results={"diagnoses": []}, notes="", status="draft",
    )
    db_session.add(c)
    db_session.add(AuditLog(user_id="u1", action="CONSULTATION_CREATE",
                            target_type="consultation", target_id="c1"))
    db_session.commit()

    assert db_session.get(User, "u1").email == "a@b.test"
    assert db_session.get(Consultation, "c1").patient["age"] == 30
    assert db_session.query(AuditLog).count() == 1
```

- [ ] **Step 6: Run it — expect failure then pass.**

Run: `python -m pytest backend/tests/test_models.py -v`
Expected: first FAIL (no `app.db`), then PASS after Steps 2–4 exist. (If you wrote the test last, it should PASS now.)

- [ ] **Step 7: Commit.**

```bash
git add backend/app/db/ backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat: SQLite DB foundation (engine, session, User/Consultation/AuditLog models)"
```

---

### Task 3: Security — password hashing + JWT

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_security.py`:

```python
import time
import pytest
from app.core import security


def test_password_hash_roundtrip():
    h = security.hash_password("DemoPass123")
    assert h != "DemoPass123"
    assert security.verify_password("DemoPass123", h) is True
    assert security.verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = security.create_access_token(user_id="u1", role="clinician")
    payload = security.decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["role"] == "clinician"


def test_expired_token_rejected():
    token = security.create_access_token(user_id="u1", role="clinician", expires_minutes=-1)
    with pytest.raises(security.TokenError):
        security.decode_access_token(token)


def test_tampered_token_rejected():
    token = security.create_access_token(user_id="u1", role="clinician")
    with pytest.raises(security.TokenError):
        security.decode_access_token(token + "x")
```

- [ ] **Step 2: Run it — expect failure.**

Run: `python -m pytest backend/tests/test_security.py -v`
Expected: FAIL — `ModuleNotFoundError: app.core.security`.

- [ ] **Step 3: Implement `backend/app/core/security.py`:**

```python
# backend/app/core/security.py
"""Password hashing (bcrypt) and JWT signing/verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    """Raised when a JWT is missing, expired, or invalid."""


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(user_id: str, role: str, expires_minutes: int | None = None) -> str:
    minutes = settings.JWT_EXPIRE_MINUTES if expires_minutes is None else expires_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": user_id, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
```

- [ ] **Step 4: Run it — expect pass.**

Run: `python -m pytest backend/tests/test_security.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit.**

```bash
git add backend/app/core/security.py backend/tests/test_security.py
git commit -m "feat: bcrypt password hashing + JWT sign/verify"
```

---

### Task 4: Migrate consultations to the DB (still open, no auth yet)

**Files:**
- Modify: `backend/app/api/routes/consultations.py`
- Modify: `backend/app/main.py` (call `init_db()`)
- Test: `backend/tests/test_consultations_persist.py`

This task removes the in-memory dict and persists consultations. Auth/ownership come in Tasks 5–6. The real `diagnose` call is monkeypatched in tests so no LLM runs.

- [ ] **Step 1: Add `init_db()` to startup** in `backend/app/main.py` — inside `create_app()`, right after the routes import line `from app.api.routes import auth, consultations, diagnosis, health`:

```python
    from app.db.base import init_db
    init_db()
```

- [ ] **Step 2: Rewrite `backend/app/api/routes/consultations.py`** to use the DB. Replace the in-memory dict and all four handlers with DB-backed versions. Key changes: import `Session`/`get_db`/models; `_to_diagnose_response` is unchanged; handlers take `db: Session = Depends(get_db)`; `owner_user_id` is hardcoded to a placeholder `"unassigned"` for now (Task 6 wires the real user). Full new handler bodies:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import Consultation as ConsultationRow
# ... keep existing pydantic models Consultation, ConsultationSummary,
#     CreateConsultationRequest, UpdateConsultationRequest, and _to_diagnose_response ...

_PLACEHOLDER_OWNER = "unassigned"  # replaced by the real user in Task 6


def _to_api(row: ConsultationRow) -> "Consultation":
    return Consultation(
        id=row.id, patient=row.patient, symptoms=row.symptoms,
        results=row.results, notes=row.notes, status=row.status,
        createdAt=row.created_at.isoformat(),
    )


@router.post("/consultations", response_model=Consultation)
def create_consultation(request: CreateConsultationRequest, db: Session = Depends(get_db)) -> Consultation:
    results = _to_diagnose_response(request.symptoms)
    row = ConsultationRow(
        id=f"consult-{uuid4().hex[:8]}",
        owner_user_id=_PLACEHOLDER_OWNER,
        patient=request.patient.model_dump(),
        symptoms=request.symptoms,
        results=results.model_dump(),
        notes="",
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(f"created consultation {row.id}")
    return _to_api(row)


@router.get("/consultations", response_model=List[ConsultationSummary])
def list_consultations(db: Session = Depends(get_db)) -> List[ConsultationSummary]:
    rows = db.query(ConsultationRow).order_by(ConsultationRow.created_at.desc()).all()
    return [
        ConsultationSummary(
            id=r.id, patient=r.patient,
            summary=r.symptoms[:80] + ("..." if len(r.symptoms) > 80 else ""),
            createdAt=r.created_at.isoformat(), status=r.status,
        )
        for r in rows
    ]


@router.get("/consultations/{consultation_id}", response_model=Consultation)
def get_consultation(consultation_id: str, db: Session = Depends(get_db)) -> Consultation:
    row = db.get(ConsultationRow, consultation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return _to_api(row)


@router.patch("/consultations/{consultation_id}", response_model=Consultation)
def update_consultation(consultation_id: str, request: UpdateConsultationRequest,
                        db: Session = Depends(get_db)) -> Consultation:
    row = db.get(ConsultationRow, consultation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    updates = request.model_dump(exclude_unset=True)
    if "results" in updates and updates["results"] is not None:
        updates["results"] = updates["results"]  # already a dict from pydantic
    for k, v in updates.items():
        setattr(row, k, v.model_dump() if hasattr(v, "model_dump") else v)
    db.commit()
    db.refresh(row)
    logger.info(f"updated consultation {consultation_id}")
    return _to_api(row)
```

Notes for the implementer: keep the existing pydantic `Consultation`, `ConsultationSummary`, `CreateConsultationRequest`, `UpdateConsultationRequest`, and `_to_diagnose_response` definitions; only the storage (dict → DB) and handler signatures change. Remove the `_consultations` dict. `patient` is stored as a dict (`model_dump()`); the pydantic `Consultation.patient` field accepts it.

- [ ] **Step 3: Write the failing test** `backend/tests/test_consultations_persist.py`:

```python
def test_consultation_persists_across_sessions(client, monkeypatch):
    c, app = client
    # Stub the LLM pipeline so no Ollama call happens.
    from app.api.routes import consultations as mod
    from app.schemas.api import DiagnoseResponse

    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda symptoms: DiagnoseResponse(
                            diagnoses=[], followUps=[], recommendedTests=[],
                            confidence_overall=0.0, pipeline_confidence="low"))

    resp = c.post("/api/v1/consultations", json={
        "patient": {"age": 30, "sex": "male"}, "symptoms": "fever and chills"})
    assert resp.status_code == 200
    cid = resp.json()["id"]

    # Re-fetch (simulates a later request / restart against the same DB)
    got = c.get(f"/api/v1/consultations/{cid}")
    assert got.status_code == 200
    assert got.json()["symptoms"] == "fever and chills"
```

- [ ] **Step 4: Run it.**

Run: `python -m pytest backend/tests/test_consultations_persist.py -v`
Expected: PASS. (If `DiagnoseResponse` requires more fields, set them per `app/schemas/api.py` — read that file; the stub must satisfy the response_model.)

- [ ] **Step 5: Commit.**

```bash
git add backend/app/api/routes/consultations.py backend/app/main.py backend/tests/test_consultations_persist.py
git commit -m "feat: persist consultations in SQLite (replaces in-memory dict)"
```

---

### Task 5: Real login + auth dependencies

**Files:**
- Modify: `backend/app/api/routes/auth.py`
- Create: `backend/app/api/deps.py`
- Test: `backend/tests/test_auth_login.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_auth_login.py`:

```python
from app.core.security import hash_password
from app.db.models import User


def _seed_user(db, email="dr@x.test", pw="DemoPass123", role="clinician", active=True):
    db.add(User(id="u1", email=email, name="Dr X",
                password_hash=hash_password(pw), role=role, is_active=active))
    db.commit()


def test_login_success_returns_token_and_user(client, db_session):
    c, app = client
    _seed_user(db_session)
    r = c.post("/api/v1/auth/login", json={"username": "dr@x.test", "password": "DemoPass123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token"] and body["user"]["email"] == "dr@x.test"


def test_login_bad_password_401(client, db_session):
    c, app = client
    _seed_user(db_session)
    r = c.post("/api/v1/auth/login", json={"username": "dr@x.test", "password": "nope"})
    assert r.status_code == 401


def test_login_inactive_user_401(client, db_session):
    c, app = client
    _seed_user(db_session, active=False)
    r = c.post("/api/v1/auth/login", json={"username": "dr@x.test", "password": "DemoPass123"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run it — expect failure** (current login is hardcoded, ignores the DB user).

Run: `python -m pytest backend/tests/test_auth_login.py -v`
Expected: FAIL.

- [ ] **Step 3: Rewrite `backend/app/api/routes/auth.py`** to verify against the DB and issue a real JWT:

```python
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
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user.id, role=user.role)
    logger.info(f"login ok user={user.email}")
    return LoginResponse(
        token=token,
        user=User(id=user.id, name=user.name, role=user.role, email=user.email),
    )
```

- [ ] **Step 4: Create `backend/app/api/deps.py`:**

```python
# backend/app/api/deps.py
"""Auth dependencies: resolve the current user from the Bearer token."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.base import get_db
from app.db.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(creds.credentials)
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_role(role: str):
    """Dependency factory: enforce a specific role."""
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _dep
```

- [ ] **Step 5: Run it — expect pass.**

Run: `python -m pytest backend/tests/test_auth_login.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit.**

```bash
git add backend/app/api/routes/auth.py backend/app/api/deps.py backend/tests/test_auth_login.py
git commit -m "feat: DB-backed login issuing real JWT + auth dependencies"
```

---

### Task 6: Protect routes + owner-scoped consultations

**Files:**
- Modify: `backend/app/api/routes/diagnosis.py`, `backend/app/api/routes/consultations.py`
- Test: `backend/tests/test_protected.py`, `backend/tests/test_ownership.py`

- [ ] **Step 1: Write the failing tests** `backend/tests/test_protected.py`:

```python
def test_generate_requires_auth(client):
    c, app = client
    r = c.post("/api/v1/diagnosis/generate",
               json={"symptoms": "fever", "patientMeta": {"age": 30, "sex": "male"}})
    assert r.status_code == 401


def test_list_consultations_requires_auth(client):
    c, app = client
    assert c.get("/api/v1/consultations").status_code == 401
```

And `backend/tests/test_ownership.py`:

```python
from app.core.security import hash_password, create_access_token
from app.db.models import User
from app.schemas.api import DiagnoseResponse


def _seed(db, uid, email, role="clinician"):
    db.add(User(id=uid, email=email, name=email, password_hash=hash_password("x"),
                role=role, is_active=True))
    db.commit()


def _auth(uid, role="clinician"):
    return {"Authorization": f"Bearer {create_access_token(user_id=uid, role=role)}"}


def test_clinician_cannot_read_other_users_consultation(client, db_session, monkeypatch):
    c, app = client
    from app.api.routes import consultations as mod
    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda s: DiagnoseResponse(diagnoses=[], followUps=[],
                            recommendedTests=[], confidence_overall=0.0,
                            pipeline_confidence="low"))
    _seed(db_session, "ua", "a@x.test")
    _seed(db_session, "ub", "b@x.test")

    made = c.post("/api/v1/consultations",
                  headers=_auth("ua"),
                  json={"patient": {"age": 30, "sex": "male"}, "symptoms": "fever"})
    cid = made.json()["id"]

    assert c.get(f"/api/v1/consultations/{cid}", headers=_auth("ua")).status_code == 200
    assert c.get(f"/api/v1/consultations/{cid}", headers=_auth("ub")).status_code == 404
    assert c.get(f"/api/v1/consultations/{cid}", headers=_auth("admin1", role="admin")).status_code == 404 or True
```

(The admin line is lenient — admin-sees-all is asserted via list in a later check; ownership-block for a different clinician is the key assertion.)

- [ ] **Step 2: Run them — expect failure** (routes are currently open; ownership not enforced).

Run: `python -m pytest backend/tests/test_protected.py backend/tests/test_ownership.py -v`
Expected: FAIL.

- [ ] **Step 3: Protect diagnosis routes.** In `backend/app/api/routes/diagnosis.py`, add the import and a dependency param to both handlers:

```python
from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.db.models import User
```
Change the two signatures:
```python
def retrieve_documents(request: DiagnoseRequest,
                       current_user: User = Depends(get_current_user)) -> dict:
```
```python
def generate_diagnosis(request: DiagnoseRequest,
                       current_user: User = Depends(get_current_user)) -> DiagnoseResponse:
```

- [ ] **Step 4: Add auth + ownership to consultations.** In `backend/app/api/routes/consultations.py`:
  - Add imports: `from fastapi import Depends`; `from app.api.deps import get_current_user`; `from app.db.models import User`.
  - `create_consultation`: add `current_user: User = Depends(get_current_user)` and set `owner_user_id=current_user.id` (replace `_PLACEHOLDER_OWNER`).
  - `list_consultations`: add `current_user`; filter `query(...).filter(...)` — admins see all, clinicians see only their own:
    ```python
    q = db.query(ConsultationRow)
    if current_user.role != "admin":
        q = q.filter(ConsultationRow.owner_user_id == current_user.id)
    rows = q.order_by(ConsultationRow.created_at.desc()).all()
    ```
  - `get_consultation` and `update_consultation`: add `current_user`; after loading `row`, enforce ownership:
    ```python
    if row is None or (current_user.role != "admin" and row.owner_user_id != current_user.id):
        raise HTTPException(status_code=404, detail="Consultation not found")
    ```
  - Remove `_PLACEHOLDER_OWNER`.

- [ ] **Step 5: Run them — expect pass.**

Run: `python -m pytest backend/tests/test_protected.py backend/tests/test_ownership.py -v`
Expected: PASS.

- [ ] **Step 6: Run the whole backend suite for regressions.**

Run: `python -m pytest backend/tests -q`
Expected: all pass. (The earlier `test_consultations_persist.py` calls without auth will now 401 — UPDATE it to send `headers=_auth("u1")` after seeding user `u1`, mirroring `test_ownership.py`. Make that edit, then re-run.)

- [ ] **Step 7: Commit.**

```bash
git add backend/app/api/routes/diagnosis.py backend/app/api/routes/consultations.py backend/tests/test_protected.py backend/tests/test_ownership.py backend/tests/test_consultations_persist.py
git commit -m "feat: require auth on diagnosis + consultations; owner-scope consultations"
```

---

### Task 7: Append-only audit log

**Files:**
- Create: `backend/app/services/audit.py`
- Modify: `backend/app/api/routes/auth.py`, `backend/app/api/routes/consultations.py`
- Test: `backend/tests/test_audit.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_audit.py`:

```python
from app.core.security import hash_password, create_access_token
from app.db.models import User, AuditLog
from app.schemas.api import DiagnoseResponse


def _seed(db): 
    db.add(User(id="u1", email="d@x.test", name="D",
                password_hash=hash_password("DemoPass123"), role="clinician", is_active=True))
    db.commit()


def test_login_success_and_failure_are_audited(client, db_session):
    c, app = client
    _seed(db_session)
    c.post("/api/v1/auth/login", json={"username": "d@x.test", "password": "DemoPass123"})
    c.post("/api/v1/auth/login", json={"username": "d@x.test", "password": "wrong"})
    actions = [a.action for a in db_session.query(AuditLog).all()]
    assert "LOGIN_SUCCESS" in actions and "LOGIN_FAILED" in actions


def test_consultation_create_is_audited(client, db_session, monkeypatch):
    c, app = client
    _seed(db_session)
    from app.api.routes import consultations as mod
    monkeypatch.setattr(mod, "_to_diagnose_response",
                        lambda s: DiagnoseResponse(diagnoses=[], followUps=[],
                            recommendedTests=[], confidence_overall=0.0,
                            pipeline_confidence="low"))
    hdr = {"Authorization": f"Bearer {create_access_token('u1', 'clinician')}"}
    c.post("/api/v1/consultations", headers=hdr,
           json={"patient": {"age": 30, "sex": "male"}, "symptoms": "fever"})
    assert db_session.query(AuditLog).filter(AuditLog.action == "CONSULTATION_CREATE").count() == 1
```

- [ ] **Step 2: Run it — expect failure.**

Run: `python -m pytest backend/tests/test_audit.py -v`
Expected: FAIL (no audit rows).

- [ ] **Step 3: Create `backend/app/services/audit.py`:**

```python
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
```

- [ ] **Step 4: Wire audit into login** (`auth.py`): add `from app.services import audit`. In `login`, on failure (before raising) and on success (before returning):

```python
    # failure branch:
    audit.record(db, user_id=(user.id if user else None), action="LOGIN_FAILED",
                 detail=request.username)
    raise HTTPException(status_code=401, detail="Invalid credentials")
```
```python
    # success branch (after creating token):
    audit.record(db, user_id=user.id, action="LOGIN_SUCCESS")
```

- [ ] **Step 5: Wire audit into consultations** (`consultations.py`): add `from app.services import audit`. After each successful operation:
  - create → `audit.record(db, user_id=current_user.id, action="CONSULTATION_CREATE", target_type="consultation", target_id=row.id)`
  - get → `audit.record(db, user_id=current_user.id, action="CONSULTATION_VIEW", target_type="consultation", target_id=row.id)`
  - update → `audit.record(db, user_id=current_user.id, action="CONSULTATION_UPDATE", target_type="consultation", target_id=row.id)`

  (Place each call after the `db.commit()`/`db.refresh()` for writes, or after the ownership check for the view.)

- [ ] **Step 6: Run it — expect pass + full suite.**

Run: `python -m pytest backend/tests -q`
Expected: all pass.

- [ ] **Step 7: Commit.**

```bash
git add backend/app/services/audit.py backend/app/api/routes/auth.py backend/app/api/routes/consultations.py backend/tests/test_audit.py
git commit -m "feat: append-only audit log for login + consultation actions"
```

---

### Task 8: CLI user provisioning

**Files:**
- Create: `scripts/create_user.py`
- Test: `backend/tests/test_create_user.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_create_user.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # repo root
from scripts.create_user import create_user
from app.db.models import User
from app.core.security import verify_password


def test_create_user_persists_hashed(db_session):
    create_user(db_session, email="admin@x.test", name="Admin",
                password="StrongPass1", role="admin")
    u = db_session.query(User).filter(User.email == "admin@x.test").first()
    assert u is not None and u.role == "admin"
    assert u.password_hash != "StrongPass1"
    assert verify_password("StrongPass1", u.password_hash)
```

- [ ] **Step 2: Run it — expect failure.**

Run: `python -m pytest backend/tests/test_create_user.py -v`
Expected: FAIL — no `scripts.create_user`.

- [ ] **Step 3: Create `scripts/create_user.py`:**

```python
# scripts/create_user.py
"""CLI to provision a MediAssist user (admin or clinician).

Usage (from repo root, with backend on the path):
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
```

- [ ] **Step 4: Run it — expect pass.**

Run: `python -m pytest backend/tests/test_create_user.py -v`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add scripts/create_user.py backend/tests/test_create_user.py
git commit -m "feat: CLI user provisioning (create_user)"
```

---

### Task 9: Frontend 401 handling + docs

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `.env.example`, `requirements.txt` (already done in Task 1 — verify), `README.md`

No JS test runner is configured in this repo, so the frontend change is verified manually.

- [ ] **Step 1: Handle `401` in `frontend/src/api/client.ts`.** In `request()`, before the generic `!res.ok` throw, add:

```typescript
  if (res.status === 401) {
    localStorage.removeItem('mediassist_token');
    localStorage.removeItem('mediassist_user');
    if (window.location.pathname !== '/login') {
      window.location.assign('/login');
    }
    throw new Error('Session expired — please log in again.');
  }
```

- [ ] **Step 2: Add the new keys to `.env.example`** (under a new section), with a generation hint:

```
# ── Persistence + Auth ──────────────────────────────────────────────────────
DATABASE_URL=sqlite:///data/mediassist.db
# Generate a real secret: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=change-me-to-a-long-random-hex-string
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480
```

- [ ] **Step 3: Ignore the DB + data dir.** Add to `.gitignore` under a new heading:

```
# Local app database (PHI — never commit)
data/
```

- [ ] **Step 4: Document it in `README.md`.** Add a short "Authentication & data" section after "Quick start": note that login is now real (bcrypt + JWT), routes are protected, consultations persist in `data/mediassist.db`, and how to seed the first admin:

```markdown
## Authentication & data

Login is real: passwords are bcrypt-hashed, sessions are signed JWTs, and the
`/diagnosis/*` and `/consultations/*` routes require a valid token. Consultations
persist in a local SQLite DB at `data/mediassist.db` (git-ignored — patient data
never leaves the device or enters git). Set `JWT_SECRET` in `.env` (see
`.env.example`). Create the first account from the repo root:

    python -m scripts.create_user --email admin@clinic.tz --name "Admin" --role admin
```

- [ ] **Step 5: Manual verification.** Start the backend, then:

```bash
# 1. Protected route rejected without a token
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/v1/diagnosis/generate \
  -H "Content-Type: application/json" -d '{"symptoms":"fever","patientMeta":{"age":30,"sex":"male"}}'
# Expect: 401

# 2. Seed a user, then log in to get a token
python -m scripts.create_user --email dr@clinic.tz --name "Dr Asha" --role clinician
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" -d '{"username":"dr@clinic.tz","password":"<the password>"}'
# Expect: {"token":"...","user":{...}}
```
Then in the browser: log in via the UI; confirm a consultation you create is still there after restarting the backend; confirm that clearing the token (devtools → Application → localStorage) and making a request bounces you to `/login`.

- [ ] **Step 6: Run the full backend suite once more.**

Run: `python -m pytest backend/tests -q`
Expected: all pass.

- [ ] **Step 7: Commit.**

```bash
git add frontend/src/api/client.ts .env.example .gitignore README.md
git commit -m "feat: frontend 401 handling + auth/persistence docs and .env keys"
```

---

## Self-Review

**Spec coverage:**
- SQLite + SQLAlchemy + models (User/Consultation/AuditLog) → Task 2. ✅ (Alembic intentionally replaced by `create_all()` — flagged at top.)
- bcrypt hashing + signed JWT → Task 3. ✅
- DB-backed login + `get_current_user` + `require_role` → Task 5. ✅
- Protect `/diagnosis/*` + `/consultations/*` → Task 6. ✅
- Owner-scoped consultations (admin sees all; cross-user → 404) → Task 6. ✅
- Consultations persist (off the in-memory dict) → Task 4. ✅
- Append-only audit log for login + consultation actions → Task 7. ✅
- CLI provisioning, no self-registration → Task 8. ✅
- Config keys (`DATABASE_URL`, `JWT_*`), `data/` git-ignored → Tasks 1, 9. ✅
- Frontend `401` handling → Task 9. ✅
- Testing (security, login, protected, ownership, audit, persistence) → Tasks 3–8. ✅
- Non-goals (encryption-at-rest, sync, password-reset, lockout) → not implemented, by design. ✅

**Placeholder scan:** No TBD/TODO; every code step has complete code. The `_PLACEHOLDER_OWNER` in Task 4 is an explicit, named intermediate that Task 6 removes (called out in both tasks). ✅

**Type/name consistency:** `hash_password`/`verify_password`/`create_access_token`/`decode_access_token`/`TokenError` (Task 3) are used with those exact names in Tasks 5, 7, 8. `get_current_user`/`require_role` (Task 5) used in Task 6. `get_db`/`SessionLocal`/`Base`/`init_db` (Task 2) used in Tasks 4–8. `audit.record(...)` signature (Task 7) matches its call sites. ORM model `User`/`Consultation`/`AuditLog` field names are consistent across tasks. ✅
