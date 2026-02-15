"""
Booking Domain — Pydantic Request / Response Schemas.

Strict contracts for availability management, appointment booking,
and status updates.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Availability ───────────────────────────────────────────────

class AvailabilitySlot(BaseModel):
    """A single recurring weekly availability window."""
    day_of_week: int = Field(..., ge=1, le=7, description="1=Mon … 7=Sun")
    start_hour: int = Field(..., ge=0, le=23)
    end_hour: int = Field(..., ge=1, le=23)
    slot_duration_min: int = Field(default=30, ge=15, le=120)


class SetAvailabilityRequest(BaseModel):
    """Batch-set weekly availability (replaces existing schedule)."""
    slots: list[AvailabilitySlot] = Field(..., min_length=1)


class AvailabilityResponse(BaseModel):
    """Single availability slot response."""
    id: UUID
    professional_id: UUID
    day_of_week: int
    start_hour: int
    end_hour: int
    slot_duration_min: int

    model_config = {"from_attributes": True}


class WeeklyScheduleResponse(BaseModel):
    """Full weekly schedule for a professional."""
    professional_id: UUID
    slots: list[AvailabilityResponse]


# ── Bookable Time Slots (computed from Availability) ──────────

class TimeSlot(BaseModel):
    """A concrete bookable time window (generated from availability)."""
    start_time: datetime
    end_time: datetime
    is_available: bool = True


class AvailableSlotsResponse(BaseModel):
    """Available time slots for a professional on a given date."""
    professional_id: UUID
    date: str
    slots: list[TimeSlot]


# ── Appointment Booking ───────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    """Patient booking payload."""
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentResponse(BaseModel):
    """Appointment data returned to clients."""
    id: UUID
    patient_id: UUID
    professional_id: UUID
    start_time: datetime
    end_time: datetime
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Status Update ──────────────────────────────────────────────

class UpdateStatusRequest(BaseModel):
    """Professional confirms, declines, or completes an appointment."""
    status: str = Field(
        ...,
        pattern=r"^(confirmed|declined|cancelled|completed)$",
        description="One of: confirmed, declined, cancelled, completed",
    )


class AppointmentListResponse(BaseModel):
    """Paginated list of appointments."""
    appointments: list[AppointmentResponse]
    total: int
