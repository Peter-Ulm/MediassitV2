"""
Auth routes — minimal demo-grade implementation.

For the FYP demo this is intentionally a mocked credential check that mirrors
the MSW fixture the frontend uses standalone:

    email:    dr.demo@mediassist.test
    password: DemoPass123

For a real deployment, replace with a proper user store + JWT signing. The
route shape is stable so the frontend does not need to change.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logger import logger

router = APIRouter()


# Hardcoded demo credentials. Matches frontend/src/mocks/handlers.ts so the
# same login works whether the frontend is running on MSW mocks or live.
_DEMO_EMAIL = "dr.demo@mediassist.test"
_DEMO_PASSWORD = "DemoPass123"
_DEMO_TOKEN = "demo-jwt-token-dr-demo-2026"


class LoginRequest(BaseModel):
    username: str
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
def login(request: LoginRequest) -> LoginResponse:
    if request.username == _DEMO_EMAIL and request.password == _DEMO_PASSWORD:
        logger.info(f"login ok user={request.username}")
        return LoginResponse(
            token=_DEMO_TOKEN,
            user=User(
                id="user-demo-001",
                name="Dr. Demo",
                role="doctor",
                email=request.username,
            ),
        )

    logger.warning(f"login failed user={request.username}")
    raise HTTPException(status_code=401, detail="Invalid credentials")
