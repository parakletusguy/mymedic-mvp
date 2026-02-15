"""
Marketplace Domain — SQL Models.

ProfessionalProfile is a 1:1 extension of the Identity User model.
It stores searchable, public-facing data about verified professionals.

IMPORTANT: This model does NOT own the User row — it references it
via a foreign key. The Identity Agent owns user creation.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class ProfessionalProfile(Base):
    """
    Public professional profile linked 1:1 to a User with role='professional'.

    Fields
    ------
    id : UUID               Primary key.
    user_id : UUID           FK → users.id (unique, enforcing 1:1).
    specialty : str          Primary medical specialty (searchable).
    sub_specialties : str    Comma-separated secondary specialties.
    bio : str                Free-text professional biography.
    license_number : str     Medical license ID for verification.
    years_of_experience : int
    consultation_fee : float Default fee in USD.
    is_verified : bool       Admin-toggled after license check.
    avatar_url : str         Profile photo URL.
    rating : float           Aggregate patient rating (0.0–5.0).
    review_count : int       Total reviews received.
    created_at : datetime
    updated_at : datetime
    """

    __tablename__ = "professional_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    specialty: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    sub_specialties: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    license_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    years_of_experience: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    consultation_fee: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    rating: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    review_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
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

    # ── Relationship to Identity User ──────────────────────────
    user = relationship("User", backref="professional_profile", lazy="joined")

    def __repr__(self) -> str:
        return f"<ProfessionalProfile {self.specialty} user={self.user_id}>"
