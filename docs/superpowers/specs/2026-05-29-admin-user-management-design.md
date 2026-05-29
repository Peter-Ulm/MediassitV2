# In-App Admin — User Management — Design

**Date:** 2026-05-29
**Status:** Approved (design); pending implementation plan
**Branch:** `admin-user-management` (based on `fix-onboarding-deps`)
**Prerequisite:** the `fix-onboarding-deps` PR should be merged first (it provides `scripts/seed_demo.py`, which this feature extends, plus the `rank_bm25` fix the app needs to run). This branch is based on it so the work is buildable regardless.

## Problem

Accounts can currently only be created from the CLI (`scripts/create_user.py`). There is no way for an administrator to manage users from inside the app — create accounts, disable a departed clinician, change a role, or reset a forgotten password. For a real (non-developer) administrator, CLI-only provisioning is a dead end.

## Goal

An **admin-only** in-app user-management screen, backed by a guarded admin API, that lets an administrator: list users, create accounts, activate/deactivate accounts, change a user's role, and reset a password. The first admin is still bootstrapped via the CLI (you cannot use an admin-only screen without an admin); a demo admin is seeded so the screen is demoable out of the box.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Full management: list, create, activate/deactivate, change role, reset password |
| Hard-delete | **Excluded** — deleting a user breaks `Consultation.owner_user_id` / `AuditLog.user_id` references; **deactivate** is the correct, audit-preserving equivalent |
| Self-protection | An admin cannot **deactivate themselves** or **demote themselves** from admin (prevents lock-out) |
| Bootstrap | First real admin via CLI (`create_user --role admin`); **also seed a demo admin** (`admin.demo@mediassist.test` / `DemoPass123`) alongside the demo clinician |
| Logic location | Extract a shared `app/services/users.py` used by **both** the API and the CLI (one source of truth) |
| Access | Admin API guarded by the existing `require_role("admin")`; frontend route + nav link gated on `user.role === 'admin'` |

## Non-goals (YAGNI)

- Hard-delete of users (see above).
- Email-based password reset / password-reset tokens (admin sets a new password directly).
- Pagination / search / filtering (small user base).
- Per-user permissions beyond the existing two roles (`clinician`, `admin`).

## Architecture

A new admin area: backend admin API (guarded) + a role-guarded frontend page at `/admin`. User-management logic lives in one service used by the API and the CLI. Every mutating action writes an audit row.

### Backend

**`backend/app/services/users.py`** (new — single source of truth):
- `create_user(db, *, email, name, password, role) -> User` — moved from `scripts/create_user.py`; validates `role ∈ {clinician, admin}`, rejects duplicate email, hashes the password. `scripts/create_user.py` and `scripts/seed_demo.py` import from here (CLI behavior unchanged).
- `list_users(db) -> list[User]`
- `set_active(db, user_id, is_active: bool) -> User`
- `set_role(db, user_id, role: str) -> User` (validates role)
- `reset_password(db, user_id, new_password: str) -> User`
- Lookups raise a `UserNotFound` (→ 404) / `ValueError` (→ 400) the routes translate to HTTP.

**`backend/app/api/routes/admin.py`** (new — every route `Depends(require_role("admin"))`):
- `GET  /admin/users` → `list[UserOut]`
- `POST /admin/users` → body `{email, name, password, role}` → `UserOut`
- `PATCH /admin/users/{user_id}` → body `{isActive?: bool, role?: str}` → `UserOut`
- `POST /admin/users/{user_id}/reset-password` → body `{password}` → `{ "ok": true }`
- **`UserOut`** pydantic model: `id, email, name, role, isActive, createdAt` — **never** includes `password_hash`. (`isActive`/`createdAt` via field aliases so the JSON is camelCase, matching the frontend's existing convention.)
- **Self-protection:** in `PATCH`, if `user_id == current_admin.id` and (`isActive` is `False` or `role` != `"admin"`) → `400 "You cannot deactivate or demote your own admin account."`
- **Audit** (via `app/services/audit.py`): `USER_CREATE`, `USER_UPDATE` (detail = changed fields), `USER_RESET_PASSWORD`, each with `user_id = current_admin.id`, `target_type="user"`, `target_id=<user_id>`.
- Registered in `backend/app/main.py` alongside the other routers (prefix `/api/v1`).

### Frontend

- **`frontend/src/pages/admin-users.tsx`** (new): a users table (name + email, role badge, active/inactive status), with
  - a **Create user** form (email, name, password, role select),
  - per-row **Activate / Deactivate** toggle,
  - **Change role** control (clinician ↔ admin),
  - **Reset password** action (prompts for a new password).
  Uses the existing Tailwind design system (teal accents, cards) seen in `login.tsx` / `dashboard.tsx`. The current admin's own row hides the self-deactivate/demote controls (mirrors the backend rule).
- **`frontend/src/routes/auth-route.tsx`** (or a new `AdminRoute`): add a role-aware guard. `AdminRoute` requires `isAuthenticated && user.role === 'admin'`; otherwise `<Navigate to="/dashboard" replace />`.
- **`frontend/src/routes/index.tsx`**: add `{ path: 'admin', element: <AdminRoute><AdminUsersPage /></AdminRoute> }` under the authed children.
- **`frontend/src/components/side-nav.tsx`**: add an "Admin" nav item, rendered **only when `user.role === 'admin'`** (read role from `useAuth`). Mirror in `mobile-nav.tsx` if it lists the same items.
- **`frontend/src/api/client.ts`** + **`types.ts`**: add `AdminUser` type and `listUsers()`, `createUser(payload)`, `updateUser(id, {isActive?, role?})`, `resetUserPassword(id, password)`.

### Bootstrap & demo

- Real admins: `python -m scripts.create_user --email a@clinic.tz --name "Admin" --role admin`.
- Extend `scripts/seed_demo.py` to also seed a **demo admin** (`admin.demo@mediassist.test` / `DemoPass123`, role `admin`) idempotently, alongside the existing demo clinician. `setup.ps1` already calls `seed_demo`, so a fresh clone gets both demo logins.
- README/login hint updated to mention the demo admin (so the admin screen is discoverable).

## Error handling

- `401` no/invalid token; `403` authenticated non-admin (from `require_role`); `404` target user not found; `400` invalid role, duplicate email, or self-deactivate/self-demote.
- Frontend: `AdminRoute` redirects non-admins away from `/admin`; API errors surface as inline messages / toasts on the admin page.
- Audit writes remain fail-safe (never break the request) per the existing `audit.record` contract.

## Testing

**Backend** (TestClient + in-memory DB, existing fixtures):
- Every admin route returns `401` without a token and `403` for a clinician token.
- `POST /admin/users` creates a user (verify via DB) and writes a `USER_CREATE` audit row; duplicate email → `400`.
- `PATCH` deactivates then reactivates a user; changes role; writes `USER_UPDATE`.
- `reset-password` sets a new password and the user can then log in with it (end-to-end through `/auth/login`).
- **Self-protection:** an admin PATCHing their own id with `isActive=false` or `role="clinician"` → `400`.
- `app/services/users.py` unit tests for `set_active` / `set_role` / `reset_password` / not-found.

**Frontend:** no JS test runner configured → manual verification (existing convention): log in as the demo admin, see the Admin nav link, create/deactivate/reset/change-role; log in as the demo clinician, confirm the Admin link and `/admin` route are not accessible.

## Success criteria

- An admin can manage users entirely from the UI (no CLI needed after the first admin exists).
- Clinicians cannot see the Admin nav link, cannot reach `/admin`, and get `403` from the admin API.
- An admin cannot lock themselves out (self-deactivate/demote blocked, server-enforced).
- Every create/update/reset is audited.
- The CLI and the admin API share one `create_user` implementation (no duplicated logic).
- A fresh clone (`setup.ps1`) has a demo admin, so the screen is demoable immediately.

## Build order (for the implementation plan)

1. `app/services/users.py` — extract `create_user` + add `list_users` / `set_active` / `set_role` / `reset_password` (+ unit tests). Update `scripts/create_user.py` and `scripts/seed_demo.py` to import from it.
2. `app/api/routes/admin.py` — guarded endpoints + `UserOut` + self-protection + audit; register in `main.py` (+ backend tests).
3. Extend `scripts/seed_demo.py` to seed the demo admin.
4. Frontend API client + types.
5. `AdminRoute` guard + `/admin` route + conditional nav link.
6. `admin-users.tsx` page (table + create form + row actions).
7. README/login hint for the demo admin; manual verification.
