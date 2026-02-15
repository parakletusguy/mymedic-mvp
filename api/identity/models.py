"""
Identity Domain — User SQL Model.

This is the GLOBAL dependency for all other agents.
Every domain that needs to reference a user should import this model.

HIPAA: password_hash is stored; plaintext is NEVER persisted.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base

import enum


class UserRole(str, enum.Enum):
    """Allowed user roles in the system."""
    PATIENT = "patient"
    PROFESSIONAL = "professional"
    ADMIN = "admin"


class User(Base):
    """
    Core User model — shared contract across all agents.

    Fields
    ------
    id : UUID          Primary key (server-generated UUID v4).
    email : str        Unique, indexed. Used for login and OTP delivery.
    password_hash : str  Bcrypt hash of the user's password.
    role : UserRole    One of patient | professional | admin.
    is_active : bool   Account not disabled / suspended.
    is_verified : bool Email verification complete.
    otp_secret : str   Per-user TOTP base32 secret (generated on registration).
    created_at : datetime  Row creation timestamp (UTC).
    updated_at : datetime  Last modification timestamp (UTC).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        default=UserRole.PATIENT,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    otp_secret: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role.value}>"
