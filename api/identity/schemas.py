"""
Identity Domain — Pydantic Request / Response Schemas.

Strict typing for mobile ↔ backend contract.
No ORM models leak to the API boundary.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator
import re


# ── Registration ───────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Patient or Professional sign-up payload."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: str = Field(default="patient", pattern=r"^(patient|professional)$")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce minimum complexity: 1 upper, 1 lower, 1 digit, 1 special."""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")
        return v


class RegisterResponse(BaseModel):
    """Acknowledgement after successful registration."""
    id: UUID
    email: str
    role: str
    message: str = "Registration successful. Please verify your email and complete 2FA on login."


# ── Login (Step 1 — credentials) ──────────────────────────────

class LoginRequest(BaseModel):
    """Email + password payload."""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """
    Returned after credentials validated but BEFORE 2FA.
    Contains a short-lived interim token to bind the OTP step.
    """
    otp_required: bool = True
    interim_token: str
    message: str = "Credentials valid. Enter the OTP sent to your email."


# ── OTP Verification (Step 2 — 2FA) ───────────────────────────

class OTPVerifyRequest(BaseModel):
    """OTP code + interim token."""
    interim_token: str
    otp_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class TokenResponse(BaseModel):
    """Final auth tokens issued after full 2FA pass."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── Token Refresh ──────────────────────────────────────────────

class RefreshRequest(BaseModel):
    refresh_token: str


# ── User (Public Read) ────────────────────────────────────────

class UserPublic(BaseModel):
    """Safe user representation — no secrets exposed."""
    id: UUID
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
