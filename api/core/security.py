"""
MyMedic Core — Security Utilities.

Provides:
  - Password hashing (bcrypt via passlib)
  - JWT creation / verification (access + refresh tokens)
  - TOTP-based OTP generation / verification (RFC 6238)

HIPAA Note: Tokens carry minimal PII (sub = user UUID only).
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from api.core.config import settings

# ── Password Hashing ──────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain* password."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return pwd_context.verify(plain, hashed)


# ── JWT Tokens ─────────────────────────────────────────────────

def _build_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: UUID, role: str) -> str:
    """Short-lived access token (default 30 min)."""
    return _build_token(
        {"sub": str(user_id), "role": role, "type": "access"},
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(user_id: UUID) -> str:
    """Long-lived refresh token (default 7 days)."""
    return _build_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT.

    Raises ``JWTError`` on invalid / expired tokens.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


# ── OTP (Time-Based One-Time Password) ────────────────────────

def generate_otp_secret() -> str:
    """Generate a per-user base32 secret for TOTP binding."""
    return pyotp.random_base32()


def generate_otp(secret: str) -> str:
    """Return the current valid OTP code for *secret*."""
    totp = pyotp.TOTP(
        secret,
        digits=settings.otp_digits,
        interval=settings.otp_interval,
        issuer=settings.otp_issuer,
    )
    return totp.now()


def verify_otp(secret: str, code: str) -> bool:
    """
    Verify an OTP code against *secret*.

    Allows ±1 time-step window to account for clock drift.
    """
    totp = pyotp.TOTP(
        secret,
        digits=settings.otp_digits,
        interval=settings.otp_interval,
        issuer=settings.otp_issuer,
    )
    return totp.verify(code, valid_window=1)
