"""
Identity Domain — Auth API Router.

Endpoints:
    POST /auth/register     — Create a new patient or professional account.
    POST /auth/login        — Validate credentials, initiate 2FA.
    POST /auth/verify-otp   — Complete 2FA, receive access + refresh tokens.
    POST /auth/refresh      — Exchange a refresh token for a new access token.
    GET  /auth/me           — Return the current authenticated user's profile.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.identity.dependencies import get_current_active_user
from api.identity.models import User
from api.identity.schemas import (
    LoginRequest,
    LoginResponse,
    OTPVerifyRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserPublic,
)
from api.identity.service import AuthService

router = APIRouter(prefix="/auth", tags=["Identity & Auth"])


# ── POST /auth/register ───────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user (Patient or Professional).",
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Creates an inactive user, hashes the password, generates an OTP secret.

    - **Patient**: Immediately usable after email verification + first 2FA.
    - **Professional**: Requires additional verification workflow (Agent 2).
    """
    return await AuthService.register(db, payload)


# ── POST /auth/login ──────────────────────────────────────────

@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate with email & password (Step 1 of 2FA).",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Validates credentials and returns an `interim_token`.

    The client MUST then call `/auth/verify-otp` with this token
    and the 6-digit OTP code to receive final access/refresh tokens.
    """
    return await AuthService.login(db, payload.email, payload.password)


# ── POST /auth/verify-otp ─────────────────────────────────────

@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    summary="Complete 2FA by submitting the OTP code (Step 2).",
)
async def verify_otp(
    payload: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Verifies the 6-digit TOTP code against the user's secret.

    On success, returns:
    - `access_token` (30-min TTL)
    - `refresh_token` (7-day TTL)
    """
    return await AuthService.verify_otp_and_issue_tokens(
        db, payload.interim_token, payload.otp_code,
    )


# ── POST /auth/refresh ────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh an access token.",
)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access token."""
    return await AuthService.refresh(db, payload.refresh_token)


# ── GET /auth/me ───────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get the current authenticated user's profile.",
)
async def me(
    current_user: User = Depends(get_current_active_user),
) -> UserPublic:
    """Returns the user's public profile. Requires a valid access token."""
    return UserPublic.model_validate(current_user)
