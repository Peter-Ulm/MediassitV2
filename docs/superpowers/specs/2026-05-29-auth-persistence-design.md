# Real Auth + Persistence Layer — Design

**Date:** 2026-05-29
**Status:** Approved (design); pending implementation plan
**Branch:** `auth-persistence` (based on `contextual-retrieval`)
**Context:** MediAssist is a single-device, offline-first clinical decision-support tool (FYP). This layer makes login real and gives the app a real database.

## Problem

Two gaps make the current app non-real:

1. **Login is cosmetic.** [backend/app/api/routes/auth.py](../../../backend/app/api/routes/auth.py) checks one hardcoded credential (`dr.demo@mediassist.test` / `DemoPass123`) and returns a *static fake token*. No password hashing, no real JWT, and **no route is protected** — `/diagnosis/*` and `/consultations/*` are open to anyone.
2. **No database for app data.** [backend/app/api/routes/consultations.py](../../../backend/app/api/routes/consultations.py) stores consultations in a process-local Python dict that is wiped on every restart. Patient meta, symptoms, diagnoses, and notes are never persisted. The only DB is ChromaDB (read-only STG knowledge base).

The data at stake (patient demographics + symptoms + diagnoses) is **PHI** under Tanzania's Personal Data Protection Act (2022), and the project's stated principle is *"offline-first — patient data never leaves the device."*

## Decisions (from brainstorming)

| Decision | Choice | Why |
|---|---|---|
| Deployment model | **One device per clinician**, offline-first | FYP; honours "data never leaves the device" |
| Database | **SQLite** + SQLAlchemy (ORM) + Alembic (migrations) | Embedded, zero-server, ideal for single-device offline-first; genuinely production-grade |
| Auth | **bcrypt** password hashing (`passlib`) + **signed JWT** (`PyJWT`) + role-protected routes | Real, standard, keeps the existing `{token, user}` frontend contract |
| PHI-safety depth | **Core + append-only audit log** | Audit (who touched which patient record) is the single most important PHI feature; cheap to add |
| Multi-user | **Multiple clinician accounts per device**, consultations **owned by their creator**; **admin** sees all + manages users | Handles solo-laptop and shared-clinic-laptop; PHI minimization |
| Provisioning | **CLI seed script** (no open self-registration) | You don't let anyone register into a clinical tool |

## Non-goals (documented fast-follows)

- **Encryption-at-rest** (SQLCipher) — deferred; SQLCipher install friction on Windows isn't worth it for the FYP. The audit log + access control are the priority.
- **Multi-device / central sync** — out of scope (offline-first single device).
- **Password-reset / email flows** — out of scope; admin re-issues a password via the CLI.
- **Account lockout / rate-limiting** — noted enhancement.

## Architecture

One **persistence + identity layer** in the backend. SQLite holds users, consultations, and an audit log. Auth issues/verifies JWTs and protects routes by role. Consultations move out of the in-memory dict into the DB. The frontend already stores the token, sends `Authorization: Bearer`, and guards routes — it needs only a `401` handler.

### Data model (3 tables)

**User**
- `id` (str/uuid, PK), `email` (unique, indexed), `name`, `password_hash`, `role` (`'clinician' | 'admin'`), `is_active` (bool, default true), `created_at`

**Consultation** (replaces the `_consultations` dict)
- `id` (str, PK), `owner_user_id` (FK → User.id, indexed), `patient` (JSON), `symptoms` (text), `results` (JSON — the `DiagnoseResponse`), `notes` (text, default ""), `status` (`'draft' | 'completed'`, default `'draft'`), `created_at`, `updated_at`

**AuditLog** (append-only — no UPDATE/DELETE in code)
- `id` (int, PK autoincrement), `user_id` (FK → User.id, nullable for failed logins), `action` (str), `target_type` (str, nullable), `target_id` (str, nullable), `timestamp`, `detail` (str, nullable)
- Actions: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `CONSULTATION_CREATE`, `CONSULTATION_VIEW`, `CONSULTATION_UPDATE`

### Auth flow

1. `POST /auth/login` (request stays `{username, password}`): look up user by email, verify password with **bcrypt** (`passlib.CryptContext`). On success, issue a **signed JWT** (`PyJWT`, claims `sub=user_id`, `role`, `exp = now + JWT_EXPIRE_MINUTES`) and return the existing `{token, user}` shape. Write `LOGIN_SUCCESS` / `LOGIN_FAILED` to the audit log. Inactive users are rejected.
2. Dependency **`get_current_user`** decodes + validates the JWT (signature, expiry), loads the user, and checks `is_active`. Invalid/expired/missing token → `401`.
3. Dependency **`require_role('admin')`** wraps `get_current_user` and enforces role for admin-only actions.
4. **Attach `get_current_user`** to every `/diagnosis/*` and `/consultations/*` route — they stop being open.

### Access control / ownership

- `create_consultation` sets `owner_user_id = current_user.id`.
- `list` / `get` / `update` consultations are filtered to the owner; an **admin** may access any. A clinician requesting another clinician's consultation gets `404` (not `403`, to avoid confirming existence).

### Provisioning

- CLI: `python -m scripts.create_user --email <e> --name <n> --role <clinician|admin>` — prompts for a password (hidden input), stores the bcrypt hash. Used to seed the first admin on a fresh device; the admin then creates clinician accounts the same way.
- (An admin-only `POST /auth/users` endpoint is a trivial later add; CLI is sufficient for the FYP.)

### Config & migrations

- New `.env` keys (`.env` is git-ignored): `DATABASE_URL=sqlite:///data/mediassist.db`, `JWT_SECRET=<generated>`, `JWT_EXPIRE_MINUTES=480`, `JWT_ALGORITHM=HS256`. `.env.example` documents them with placeholders and a note to generate `JWT_SECRET` (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).
- `data/` directory is git-ignored — **PHI is never committed.**
- **Alembic**: initial migration creates the 3 tables; future schema changes are versioned migrations, not hand-edits.
- New `requirements.txt` deps: `sqlalchemy`, `alembic`, `passlib[bcrypt]`, `pyjwt`.

### Backend module layout (new/changed)

| File | Responsibility |
|---|---|
| `backend/app/db/base.py` | SQLAlchemy engine + `SessionLocal` + `Base`; `get_db` FastAPI dependency |
| `backend/app/db/models.py` | `User`, `Consultation`, `AuditLog` ORM models |
| `backend/app/core/security.py` | password hash/verify (passlib) + JWT encode/decode (PyJWT) |
| `backend/app/api/deps.py` | `get_current_user`, `require_role` dependencies |
| `backend/app/services/audit.py` | `record(db, user_id, action, target_type, target_id, detail)` helper |
| `backend/app/api/routes/auth.py` | MODIFY — real DB-backed login + audit |
| `backend/app/api/routes/consultations.py` | MODIFY — DB-backed CRUD, ownership scoping, audit |
| `backend/app/api/routes/diagnosis.py` | MODIFY — require auth |
| `backend/app/core/config.py` | MODIFY — DB + JWT settings |
| `backend/app/main.py` | MODIFY — ensure DB ready at startup (`Base.metadata` via Alembic) |
| `alembic/` + `alembic.ini` | NEW — migrations |
| `scripts/create_user.py` | NEW — CLI provisioning |
| `frontend/src/api/client.ts` | MODIFY — on `401`, clear token/user and redirect to `/login` |

### Error handling

- Missing/invalid/expired JWT → `401` (frontend logs out + redirects).
- Wrong credentials / inactive user → `401`, `LOGIN_FAILED` audited.
- Accessing another user's consultation → `404`.
- Audit writes must never break the request path: wrap in try/except and log on failure (availability of care > audit completeness, but log the gap).

### Testing

Integration tests on a **temp SQLite DB** (fresh per test):
- `security`: hash≠plaintext, verify true/false; JWT encode→decode round-trip; expired token rejected; tampered token rejected.
- `login`: success returns `{token, user}` + writes `LOGIN_SUCCESS`; bad password → 401 + `LOGIN_FAILED`; inactive user → 401.
- `protected routes`: `/diagnosis/generate` and `/consultations` return `401` with no/invalid token; `200` with a valid token.
- `ownership`: clinician A cannot read clinician B's consultation (`404`); admin can read any.
- `audit`: create/view/update each append the expected `AuditLog` row.
- `persistence`: a consultation created, then re-fetched after a new DB session, is returned (survives "restart").

## Success criteria

- No `/diagnosis/*` or `/consultations/*` endpoint is reachable without a valid JWT.
- Passwords are bcrypt-hashed; the JWT is signed with a secret from env and verified on every protected call.
- Consultations persist across backend restarts and are scoped to their owner (admin sees all).
- Every login and every consultation create/view/update produces an audit row.
- The frontend logs the user out and returns to `/login` on a `401`.

## Build order (for the implementation plan)

1. DB foundation — SQLAlchemy `base` + `models` + Alembic init migration; `get_db` dependency.
2. Migrate consultations off the in-memory dict into the DB (CRUD still open at this step).
3. `core/security.py` — password hashing + JWT encode/decode (unit-tested in isolation).
4. Real `/auth/login` against the DB + `get_current_user` / `require_role` deps.
5. Protect `/diagnosis/*` and `/consultations/*`; add ownership scoping.
6. Audit log model + `services/audit.py` + wire into login and consultation actions.
7. `scripts/create_user.py` CLI + seed-admin docs.
8. Frontend `401` handling in `client.ts`.
9. `.env.example`, `requirements.txt`, README updates.
