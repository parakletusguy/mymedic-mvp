"""
Identity Domain — Auth Service Layer.

All business logic for registration, login, 2FA, and token refresh.
Database queries are isolated here; the router is a thin HTTP adapter.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    generate_otp_secret,
    hash_password,
    verify_otp,
    verify_password,
)
from api.core.config import settings
from api.identity.models import User, UserRole
from api.identity.schemas import (
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

from jose import JWTError
from datetime import timedelta


class AuthService:
    """Stateless service — receives an async session per call."""

    # ── Registration ───────────────────────────────────────────

    @staticmethod
    async def register(db: AsyncSession, payload: RegisterRequest) -> RegisterResponse:
        """
        Create a new inactive user.

        Steps:
          1. Check email uniqueness.
          2. Hash password (bcrypt).
          3. Generate per-user OTP secret.
          4. Persist user with is_verified=False.
          5. (TODO) Send email verification link.
        """
        # 1. Duplicate check
        existing = await db.execute(
            select(User).where(User.email == payload.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        # 2-4. Create user
        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=UserRole(payload.role),
            is_active=True,
            is_verified=False,  # Awaiting email verification
            otp_secret=generate_otp_secret(),
        )
        db.add(user)
        await db.flush()  # Populate user.id

        # 5. Email verification (stubbed — wire up SMTP in production)
        # await send_verification_email(user.email, user.id)

        return RegisterResponse(
            id=user.id,
            email=user.email,
            role=user.role.value,
        )

    # ── Login Step 1: Credentials ──────────────────────────────

    @staticmethod
    async def login(db: AsyncSession, email: str, password: str) -> LoginResponse:
        """
        Validate credentials and issue an interim token for 2FA.

        The interim token is a short-lived JWT (5 min) that binds
        the user's identity to the upcoming OTP verification step.
        """
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended. Contact support.",
            )

        # Generate & "send" OTP (in MVP, returned in logs / email stub)
        otp_code = generate_otp(user.otp_secret)

        # TODO: Send OTP via email / SMS in production
        # await send_otp_email(user.email, otp_code)
        print(f"[DEV-ONLY] OTP for {user.email}: {otp_code}")  # Remove in prod

        # Issue short-lived interim token
        from api.core.security import _build_token
        interim_token = _build_token(
            {"sub": str(user.id), "type": "interim"},
            timedelta(minutes=5),
        )

        return LoginResponse(
            otp_required=True,
            interim_token=interim_token,
        )

    # ── Login Step 2: OTP Verification ─────────────────────────

    @staticmethod
    async def verify_otp_and_issue_tokens(
        db: AsyncSession,
        interim_token: str,
        otp_code: str,
    ) -> TokenResponse:
        """
        Verify the OTP code and issue final access + refresh tokens.

        Raises 401 if OTP is invalid or interim token expired.
        """
        # Decode interim token
        try:
            payload = decode_token(interim_token)
            if payload.get("type") != "interim":
                raise JWTError("Not an interim token")
            user_id = UUID(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired interim token: {exc}",
            )

        # Fetch user
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        # Verify OTP
        if not verify_otp(user.otp_secret, otp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP code.",
            )

        # Issue real tokens
        access_token = create_access_token(user.id, user.role.value)
        refresh_token = create_refresh_token(user.id)

        # Mark verified on first successful 2FA
        if not user.is_verified:
            user.is_verified = True

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    # ── Token Refresh ──────────────────────────────────────────

    @staticmethod
    async def refresh(db: AsyncSession, refresh_token: str) -> TokenResponse:
        """
        Issue a new access token from a valid refresh token.

        The refresh token itself is NOT rotated in MVP (add rotation for prod).
        """
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise JWTError("Not a refresh token")
            user_id = UUID(payload["sub"])
        except (JWTError, KeyError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired refresh token: {exc}",
            )

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or deactivated.",
            )

        new_access = create_access_token(user.id, user.role.value)

        return TokenResponse(
            access_token=new_access,
            refresh_token=refresh_token,  # Same refresh token in MVP
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
