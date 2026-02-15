"""
Booking Domain — SQL Models.

Two core tables:
  1. Availability – recurring / one-off time windows a professional is open.
  2. Appointment  – concrete bookings linking a patient to a professional's slot.

IMPORTANT: Both tables reference User IDs from the Identity Agent.
This module does NOT own user rows.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


# ── Enums ──────────────────────────────────────────────────────

class DayOfWeek(int, enum.Enum):
    """ISO weekday numbering (1=Monday … 7=Sunday)."""
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


class AppointmentStatus(str, enum.Enum):
    """State machine: PENDING → CONFIRMED | DECLINED | CANCELLED."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# ── Availability ───────────────────────────────────────────────

class Availability(Base):
    """
    A professional's available time window.

    Represents a recurring weekly slot (day_of_week + start/end hour)
    that the Booking service uses to generate bookable time slots.

    Fields
    ------
    id : UUID
    professional_id : UUID   FK → users.id
    day_of_week : int        1 (Mon) – 7 (Sun)
    start_hour : int         0–23 (e.g. 9 = 09:00)
    end_hour : int           0–23, must be > start_hour
    slot_duration_min : int  Duration of each slot in minutes (default 30)
    """

    __tablename__ = "availabilities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    start_hour: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    end_hour: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    slot_duration_min: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Constraints ────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("day_of_week >= 1 AND day_of_week <= 7", name="ck_day_range"),
        CheckConstraint("start_hour >= 0 AND start_hour <= 23", name="ck_start_hour"),
        CheckConstraint("end_hour > start_hour AND end_hour <= 23", name="ck_end_after_start"),
        CheckConstraint("slot_duration_min > 0", name="ck_positive_duration"),
        UniqueConstraint(
            "professional_id", "day_of_week", "start_hour",
            name="uq_professional_day_start",
        ),
    )

    professional = relationship("User", backref="availabilities", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<Availability day={self.day_of_week} "
            f"{self.start_hour}:00–{self.end_hour}:00>"
        )


# ── Appointment ────────────────────────────────────────────────

class Appointment(Base):
    """
    A concrete booking between a patient and a professional.

    Fields
    ------
    id : UUID
    patient_id : UUID       FK → users.id (role=patient)
    professional_id : UUID  FK → users.id (role=professional)
    start_time : datetime   Slot start (UTC, timezone-aware)
    end_time : datetime     Slot end (UTC, timezone-aware)
    status : AppointmentStatus  PENDING | CONFIRMED | DECLINED | CANCELLED | COMPLETED
    notes : str             Optional patient notes
    """

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        SAEnum(AppointmentStatus, name="appointment_status", create_constraint=True),
        default=AppointmentStatus.PENDING,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
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

    # ── Constraints ────────────────────────────────────────────
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_end_after_start_appt"),
        # Composite index for conflict-check queries
        Index(
            "ix_appt_professional_time",
            "professional_id", "start_time", "end_time",
        ),
    )

    patient = relationship("User", foreign_keys=[patient_id], backref="patient_appointments", lazy="joined")
    professional = relationship("User", foreign_keys=[professional_id], backref="professional_appointments", lazy="joined")

    def __repr__(self) -> str:
        return f"<Appointment {self.status.value} {self.start_time}>"
