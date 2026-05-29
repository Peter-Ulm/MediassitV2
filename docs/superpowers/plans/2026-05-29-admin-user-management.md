# In-App Admin User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give administrators an in-app screen (backed by a guarded admin API) to list, create, activate/deactivate, change the role of, and reset the password of users — replacing CLI-only provisioning.

**Architecture:** A shared `app/services/users.py` holds all user-management logic and is used by both the new admin API and the existing CLI. `app/api/routes/admin.py` exposes the operations behind `require_role("admin")`, with self-lockout protection and audit logging. The frontend adds a role-guarded `/admin` page and an Admin nav link visible only to admins.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest + Starlette TestClient (backend); TypeScript/React + Tailwind (frontend, no JS test runner — manual verification).

**Spec:** [docs/superpowers/specs/2026-05-29-admin-user-management-design.md](../specs/2026-05-29-admin-user-management-design.md)

**Branch:** `admin-user-management` (based on `fix-onboarding-deps`). Merge `fix-onboarding-deps` first; this stacks on it.

**Conventions:** backend runs from `backend/` (`app.*` imports); tests run from repo root: `./.venv/Scripts/python.exe -m pytest backend/tests -q`. Roles are the literals `"clinician"` and `"admin"`.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/services/users.py` | NEW — single source of truth: create/list/set_active/set_role/reset_password + `UserNotFound`. |
| `backend/app/api/routes/admin.py` | NEW — admin-only endpoints + `UserOut` + self-protection + audit. |
| `backend/app/main.py` | MODIFY — register the admin router. |
| `scripts/create_user.py` | MODIFY — import `create_user` from the service (no duplicate logic). |
| `scripts/seed_demo.py` | MODIFY — import from the service; also seed a demo admin. |
| `backend/tests/test_users_service.py` | NEW — service unit tests. |
| `backend/tests/test_admin.py` | NEW — admin API + authz + self-protection tests. |
| `frontend/src/api/types.ts` | MODIFY — add `AdminUser`. |
| `frontend/src/api/client.ts` | MODIFY — admin API methods. |
| `frontend/src/routes/auth-route.tsx` | MODIFY — add `AdminRoute`. |
| `frontend/src/routes/index.tsx` | MODIFY — add `/admin` route. |
| `frontend/src/components/side-nav.tsx` | MODIFY — admin-only nav link. |
| `frontend/src/pages/admin-users.tsx` | NEW — the admin screen. |
| `README.md` | MODIFY — demo admin + admin screen docs. |

---

### Task 1: Shared user service (`app/services/users.py`)

**Files:**
- Create: `backend/app/services/users.py`
- Modify: `scripts/create_user.py`, `scripts/seed_demo.py`
- Test: `backend/tests/test_users_service.py`

- [ ] **Step 1: Write the failing tests** `backend/tests/test_users_service.py`:

```python
import pytest
from app.services import users
from app.core.security import verify_password


def test_create_user_hashes_and_persists(db_session):
    u = users.create_user(db_session, email="a@x.test", name="A", password="StrongPass1", role="clinician")
    assert u.password_hash != "StrongPass1"
    assert verify_password("StrongPass1", u.password_hash)
    assert u.role == "clinician" and u.is_active is True


def test_create_user_duplicate_email_raises(db_session):
    users.create_user(db_session, email="a@x.test", name="A", password="StrongPass1", role="clinician")
    with pytest.raises(ValueError):
        users.create_user(db_session, email="a@x.test", name="B", password="StrongPass1", role="clinician")


def test_create_user_bad_role_raises(db_session):
    with pytest.raises(ValueError):
        users.create_user(db_session, email="b@x.test", name="B", password="StrongPass1", role="superuser")


def test_set_active_and_set_role(db_session):
    u = users.create_user(db_session, email="c@x.test", name="C", password="StrongPass1", role="clinician")
    assert users.set_active(db_session, u.id, False).is_active is False
    assert users.set_role(db_session, u.id, "admin").role == "admin"


def test_set_role_invalid_raises(db_session):
    u = users.create_user(db_session, email="d@x.test", name="D", password="StrongPass1", role="clinician")
    with pytest.raises(ValueError):
        users.set_role(db_session, u.id, "wizard")


def test_reset_password_changes_hash(db_session):
    u = users.create_user(db_session, email="e@x.test", name="E", password="StrongPass1", role="clinician")
    users.reset_password(db_session, u.id, "NewPass2")
    assert verify_password("NewPass2", db_session.get(type(u), u.id).password_hash)


def test_missing_user_raises_usernotfound(db_session):
    with pytest.raises(users.UserNotFound):
        users.set_active(db_session, "nope", True)
```

- [ ] **Step 2: Run — expect failure.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/test_users_service.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.users`.

- [ ] **Step 3: Create `backend/app/services/users.py`:**

```python
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
```

- [ ] **Step 4: Point the CLI at the service.** Edit `scripts/create_user.py` — remove its local `create_user` definition and import the shared one. Replace the imports + function block so the file reads:

```python
# (keep the module docstring and the sys.path.insert line at the top)
from app.db.base import SessionLocal, init_db  # noqa: E402
from app.services.users import create_user  # noqa: E402  (re-exported for callers)
```
Delete the old `from app.core.security import hash_password`, `from app.db.models import User`, and the local `def create_user(...)`. Keep `main()` exactly as-is (it already calls `create_user(db, email=..., name=..., password=..., role=...)`).

- [ ] **Step 5: Point the demo seed at the service.** In `scripts/seed_demo.py`, change `from scripts.create_user import create_user` to `from app.services.users import create_user`. (The rest of seed_demo is unchanged in this task.)

- [ ] **Step 6: Run — expect pass + no regressions.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests -q`
Expected: all pass (the existing `test_create_user.py`, which imports `from scripts.create_user import create_user`, still works because that name is now re-exported from the service).

- [ ] **Step 7: Commit.**

```bash
git add backend/app/services/users.py backend/tests/test_users_service.py scripts/create_user.py scripts/seed_demo.py
git commit -m "feat: shared user-management service (used by admin API + CLI)"
```

---

### Task 2: Admin API (`app/api/routes/admin.py`)

**Files:**
- Create: `backend/app/api/routes/admin.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_admin.py`

- [ ] **Step 1: Write the failing tests** `backend/tests/test_admin.py`:

```python
from app.core.security import hash_password, create_access_token
from app.db.models import User, AuditLog
from app.services import users


def _seed(db, uid, email, role):
    db.add(User(id=uid, email=email, name=email, password_hash=hash_password("StrongPass1"),
                role=role, is_active=True))
    db.commit()


def _auth(uid):
    return {"Authorization": f"Bearer {create_access_token(user_id=uid, role='x')}"}


def test_admin_routes_require_admin(client, db_session):
    c, app = client
    _seed(db_session, "clin", "clin@x.test", "clinician")
    # no token
    assert c.get("/api/v1/admin/users").status_code == 401
    # clinician token
    assert c.get("/api/v1/admin/users", headers=_auth("clin")).status_code == 403


def test_admin_can_create_list_and_audit(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    r = c.post("/api/v1/admin/users", headers=_auth("adm"),
               json={"email": "new@x.test", "name": "New", "password": "StrongPass1", "role": "clinician"})
    assert r.status_code == 200 and r.json()["email"] == "new@x.test"
    assert "password_hash" not in r.json()
    listing = c.get("/api/v1/admin/users", headers=_auth("adm")).json()
    assert any(u["email"] == "new@x.test" for u in listing)
    assert db_session.query(AuditLog).filter(AuditLog.action == "USER_CREATE").count() == 1


def test_duplicate_email_rejected(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    body = {"email": "dup@x.test", "name": "D", "password": "StrongPass1", "role": "clinician"}
    assert c.post("/api/v1/admin/users", headers=_auth("adm"), json=body).status_code == 200
    assert c.post("/api/v1/admin/users", headers=_auth("adm"), json=body).status_code == 400


def test_patch_deactivate_and_role(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    target = users.create_user(db_session, email="t@x.test", name="T", password="StrongPass1", role="clinician")
    assert c.patch(f"/api/v1/admin/users/{target.id}", headers=_auth("adm"),
                   json={"isActive": False}).json()["isActive"] is False
    assert c.patch(f"/api/v1/admin/users/{target.id}", headers=_auth("adm"),
                   json={"role": "admin"}).json()["role"] == "admin"


def test_reset_password_lets_user_log_in(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    target = users.create_user(db_session, email="t2@x.test", name="T2", password="OldPass1", role="clinician")
    assert c.post(f"/api/v1/admin/users/{target.id}/reset-password", headers=_auth("adm"),
                  json={"password": "BrandNew2"}).status_code == 200
    assert c.post("/api/v1/auth/login", json={"username": "t2@x.test", "password": "BrandNew2"}).status_code == 200


def test_admin_cannot_lock_self_out(client, db_session):
    c, app = client
    _seed(db_session, "adm", "adm@x.test", "admin")
    assert c.patch("/api/v1/admin/users/adm", headers=_auth("adm"), json={"isActive": False}).status_code == 400
    assert c.patch("/api/v1/admin/users/adm", headers=_auth("adm"), json={"role": "clinician"}).status_code == 400
```

(Note: `_auth` signs a token whose `role` claim is ignored for authz — `require_role` reads the DB user's role. The seeded DB role is what matters.)

- [ ] **Step 2: Run — expect failure.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/test_admin.py -v`
Expected: FAIL (routes don't exist → 404, not the asserted codes).

- [ ] **Step 3: Create `backend/app/api/routes/admin.py`:**

```python
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
    isActive: bool = Field(alias="is_active")
    createdAt: datetime = Field(alias="created_at")


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
    audit.record(db, user_id=admin.id, action="USER_RESET_PASSWORD",
                 target_type="user", target_id=user_id)
    return {"ok": True}
```

- [ ] **Step 4: Register the router** in `backend/app/main.py`. Add `admin` to the route import and include it. Change the import line:
```python
    from app.api.routes import admin, auth, consultations, diagnosis, health
```
and add, next to the other `include_router` calls:
```python
    app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
```

- [ ] **Step 5: Run — expect pass + full suite.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests -q`
Expected: all pass.

- [ ] **Step 6: Commit.**

```bash
git add backend/app/api/routes/admin.py backend/app/main.py backend/tests/test_admin.py
git commit -m "feat: admin-only user-management API (list/create/update/reset) with self-lockout guard + audit"
```

---

### Task 3: Seed a demo admin

**Files:**
- Modify: `scripts/seed_demo.py`
- Test: `backend/tests/test_seed_demo.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_seed_demo.py`:

```python
from app.db.models import User
from app.services import users


def test_seed_demo_creates_clinician_and_admin(db_session, monkeypatch):
    # Point the seed at the in-memory test session.
    import scripts.seed_demo as sd
    monkeypatch.setattr(sd, "init_db", lambda: None)
    monkeypatch.setattr(sd, "SessionLocal", lambda: db_session)
    # Prevent the test session from being closed by the script.
    monkeypatch.setattr(db_session, "close", lambda: None)

    sd.main()

    emails = {u.email: u.role for u in db_session.query(User).all()}
    assert emails.get("dr.demo@mediassist.test") == "clinician"
    assert emails.get("admin.demo@mediassist.test") == "admin"
```

- [ ] **Step 2: Run — expect failure.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/test_seed_demo.py -v`
Expected: FAIL (no admin demo seeded).

- [ ] **Step 3: Extend `scripts/seed_demo.py`** to also seed the admin. Replace the constants + `main()` body so both accounts are seeded idempotently:

```python
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
```
(Keep the existing imports at the top — `create_user` now comes from `app.services.users` per Task 1; ensure `from app.db.models import User` is present for the existence check.)

- [ ] **Step 4: Run — expect pass.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests/test_seed_demo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add scripts/seed_demo.py backend/tests/test_seed_demo.py
git commit -m "feat: seed a demo admin (admin.demo@mediassist.test) so the admin screen is demoable"
```

---

### Task 4: Frontend API client + types

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`

No JS test runner — verified by inspection + the manual run in Task 7.

- [ ] **Step 1: Add the `AdminUser` type** to `frontend/src/api/types.ts` (append):

```typescript
export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: 'clinician' | 'admin';
  isActive: boolean;
  createdAt: string;
}
```

- [ ] **Step 2: Add admin methods** to the `api` object in `frontend/src/api/client.ts` (add `AdminUser` to the type import at the top, then add these methods inside the `export const api = { ... }` object):

```typescript
  listUsers: () => request<AdminUser[]>('/admin/users'),

  createUser: (payload: { email: string; name: string; password: string; role: 'clinician' | 'admin' }) =>
    request<AdminUser>('/admin/users', { method: 'POST', body: JSON.stringify(payload) }),

  updateUser: (id: string, updates: { isActive?: boolean; role?: 'clinician' | 'admin' }) =>
    request<AdminUser>(`/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(updates) }),

  resetUserPassword: (id: string, password: string) =>
    request<{ ok: boolean }>(`/admin/users/${id}/reset-password`, {
      method: 'POST', body: JSON.stringify({ password }),
    }),
```

- [ ] **Step 3: Type-check** (no runtime yet):

Run: `cd frontend; npx tsc --noEmit`
Expected: no errors. (If `tsc` isn't wired, this is verified when the dev server compiles in Task 7.)

- [ ] **Step 4: Commit.**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat: frontend admin API client (listUsers/createUser/updateUser/resetUserPassword)"
```

---

### Task 5: Admin route guard + route + nav link

**Files:**
- Modify: `frontend/src/routes/auth-route.tsx`, `frontend/src/routes/index.tsx`, `frontend/src/components/side-nav.tsx`

- [ ] **Step 1: Add `AdminRoute`** to `frontend/src/routes/auth-route.tsx` (append; keep the existing `AuthRoute`):

```typescript
export function AdminRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role !== 'admin') return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}
```

- [ ] **Step 2: Register the `/admin` route** in `frontend/src/routes/index.tsx`. Add the imports:
```typescript
import { AuthRoute, AdminRoute } from './auth-route';
import { AdminUsersPage } from '../pages/admin-users';
```
(Replace the existing `import { AuthRoute } from './auth-route';` line.) Then add this child route inside the authed `children` array (after `help`):
```typescript
      { path: 'admin', element: <AdminRoute><AdminUsersPage /></AdminRoute> },
```

- [ ] **Step 3: Add the admin-only nav link** in `frontend/src/components/side-nav.tsx`. Import `Users` from lucide and `useAuth`, then render the Admin item only for admins. Add to imports:
```typescript
import { Users } from 'lucide-react';
import { useAuth } from '../features/auth/auth-context';
```
Inside `SideNav()`, after `const [collapsed, setCollapsed] = useState(false);`, build the item list with the conditional admin entry:
```typescript
  const { user } = useAuth();
  const items = [
    ...navItems,
    ...(user?.role === 'admin' ? [{ to: '/admin', icon: Users, label: 'Admin' }] : []),
  ];
```
Then change the `.map` to iterate `items` instead of `navItems`.

- [ ] **Step 4: Type-check.**

Run: `cd frontend; npx tsc --noEmit`
Expected: no errors. (`admin-users.tsx` arrives in Task 6 — if tsc complains the module is missing, do Task 6 first or create an empty stub; the import resolves after Task 6.)

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/routes/auth-route.tsx frontend/src/routes/index.tsx frontend/src/components/side-nav.tsx
git commit -m "feat: AdminRoute guard, /admin route, admin-only nav link"
```

---

### Task 6: Admin users page (`pages/admin-users.tsx`)

**Files:**
- Create: `frontend/src/pages/admin-users.tsx`

- [ ] **Step 1: Create the page.** It lists users, creates them, toggles active, changes role, and resets passwords, using the existing Tailwind look. The current admin's own row hides the deactivate/demote controls (mirrors the server rule).

```tsx
import { useEffect, useState } from 'react';
import { api } from '../api';
import type { AdminUser } from '../api/types';
import { useAuth } from '../features/auth/auth-context';

export function AdminUsersPage() {
  const { user: me } = useAuth();
  const [usersList, setUsersList] = useState<AdminUser[]>([]);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ email: '', name: '', password: '', role: 'clinician' as 'clinician' | 'admin' });

  const load = async () => {
    try { setUsersList(await api.listUsers()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to load users'); }
  };
  useEffect(() => { load(); }, []);

  const onCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      await api.createUser(form);
      setForm({ email: '', name: '', password: '', role: 'clinician' });
      await load();
    } catch (e) { setError(e instanceof Error ? e.message : 'Create failed'); }
  };

  const toggleActive = async (u: AdminUser) => {
    setError('');
    try { await api.updateUser(u.id, { isActive: !u.isActive }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed'); }
  };

  const changeRole = async (u: AdminUser, role: 'clinician' | 'admin') => {
    setError('');
    try { await api.updateUser(u.id, { role }); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Update failed'); }
  };

  const resetPassword = async (u: AdminUser) => {
    const pw = window.prompt(`New password for ${u.email}:`);
    if (!pw) return;
    setError('');
    try { await api.resetUserPassword(u.id, pw); alert('Password reset.'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Reset failed'); }
  };

  return (
    <div className="mx-auto max-w-5xl p-6">
      <h1 className="text-2xl font-bold text-slate-900">User management</h1>
      <p className="mt-1 text-sm text-slate-500">Create and manage clinician and admin accounts.</p>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={onCreate} className="mt-6 grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-5">
        <input required type="email" placeholder="email" value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input required placeholder="name" value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <input required type="password" placeholder="password" value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm" />
        <select value={form.role}
          onChange={(e) => setForm({ ...form, role: e.target.value as 'clinician' | 'admin' })}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="clinician">clinician</option>
          <option value="admin">admin</option>
        </select>
        <button type="submit" className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-bold text-white hover:bg-teal-800">
          Create user
        </button>
      </form>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Actions</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {usersList.map((u) => {
              const isSelf = u.id === me?.id;
              return (
                <tr key={u.id}>
                  <td className="px-4 py-3"><div className="font-semibold text-slate-900">{u.name}</div><div className="text-xs text-slate-500">{u.email}</div></td>
                  <td className="px-4 py-3">
                    <select value={u.role} disabled={isSelf}
                      onChange={(e) => changeRole(u, e.target.value as 'clinician' | 'admin')}
                      className="rounded border border-slate-300 px-2 py-1 text-xs disabled:opacity-50">
                      <option value="clinician">clinician</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${u.isActive ? 'bg-teal-50 text-teal-800' : 'bg-slate-100 text-slate-500'}`}>
                      {u.isActive ? 'active' : 'inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => resetPassword(u)} className="mr-2 rounded border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50">Reset password</button>
                    <button onClick={() => toggleActive(u)} disabled={isSelf}
                      className="rounded border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
                      {u.isActive ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check + build.**

Run: `cd frontend; npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit.**

```bash
git add frontend/src/pages/admin-users.tsx
git commit -m "feat: admin user-management page (table, create form, role/active/reset actions)"
```

---

### Task 7: Docs + manual verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the admin screen + demo admin** in `README.md`. In the "Authentication & data" section, after the create-account line, add:

```markdown
Admins get an in-app **User management** screen at `/admin` (an "Admin" link
appears in the sidebar for admin accounts) to create users, activate/deactivate
them, change roles, and reset passwords. `setup.ps1` seeds a demo admin
(`admin.demo@mediassist.test` / `DemoPass123`) so the screen is demoable; the
demo clinician (`dr.demo@mediassist.test`) does **not** see it.
```

- [ ] **Step 2: Manual end-to-end verification.** Start the app (`.\scripts\run.ps1`, or backend via `python -m uvicorn app.main:app --app-dir backend` from repo root + `npm run dev` in frontend). Then:
  1. Log in as **`admin.demo@mediassist.test` / `DemoPass123`** → an **Admin** link appears in the sidebar; open `/admin`.
  2. Create a user; confirm it appears in the table.
  3. Deactivate it, change its role, reset its password.
  4. Confirm your own row's Deactivate/role controls are disabled (self-protection).
  5. Log out; log in as **`dr.demo@mediassist.test`** (clinician) → **no Admin link**, and navigating to `/admin` redirects to `/dashboard`.
  6. (API spot check) `curl` `GET /api/v1/admin/users` with a clinician token → `403`; with no token → `401`.

- [ ] **Step 3: Run the backend suite once more.**

Run: `./.venv/Scripts/python.exe -m pytest backend/tests -q`
Expected: all pass.

- [ ] **Step 4: Commit.**

```bash
git add README.md
git commit -m "docs: document the in-app admin user-management screen + demo admin"
```

---

## Self-Review

**Spec coverage:**
- Shared `app/services/users.py` (used by API + CLI) → Task 1. ✅
- Admin API: list/create/patch(activate+role)/reset-password, `require_role("admin")`, `UserOut` without password_hash → Task 2. ✅
- Self-protection (no self-deactivate/demote) → Task 2 (PATCH guard + test `test_admin_cannot_lock_self_out`). ✅
- Audit (USER_CREATE/USER_UPDATE/USER_RESET_PASSWORD) → Task 2. ✅
- Demo admin seeded → Task 3. ✅
- Frontend API client + types → Task 4. ✅
- AdminRoute guard + `/admin` route + admin-only nav → Task 5. ✅
- Admin page (table, create, activate/deactivate, change role, reset password, self-row disabled) → Task 6. ✅
- Bootstrap via CLI (unchanged), docs, manual verification → Task 7. ✅
- Non-goals (hard-delete, email reset, pagination) → not implemented, by design. ✅

**Placeholder scan:** No TBD/TODO; every code step has complete code. Frontend steps without a test runner use `tsc --noEmit` + the Task 7 manual run, which is the project's established convention. ✅

**Type/name consistency:** `users.create_user/list_users/set_active/set_role/reset_password/UserNotFound/_get` (Task 1) are used with those exact names in Task 2. `UserOut` fields (`isActive`/`createdAt` via alias) match the frontend `AdminUser` (Task 4) and the page (Task 6). API methods `listUsers/createUser/updateUser/resetUserPassword` (Task 4) are called in Task 6. `AdminRoute` (Task 5) wraps `AdminUsersPage` (Task 6). Route path `/admin` and nav `to: '/admin'` match. ✅
