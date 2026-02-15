"""
Booking Domain — API Router.

Endpoints:
    POST   /appointments/availability     — Set weekly schedule (Professional).
    GET    /appointments/availability/{id} — Get a professional's weekly schedule.
    GET    /appointments/slots/{id}        — Get bookable slots for a date.
    POST   /appointments/book              — Book an appointment (Patient).
    PATCH  /appointments/{id}/status       — Update appointment status.
    GET    /appointments                   — List own appointments.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.identity.dependencies import get_current_active_user, require_role
from api.identity.models import User
from api.booking.schemas import (
    AppointmentListResponse,
    AppointmentResponse,
    AvailableSlotsResponse,
    BookAppointmentRequest,
    SetAvailabilityRequest,
    UpdateStatusRequest,
    WeeklyScheduleResponse,
)
from api.booking.service import BookingService

router = APIRouter(prefix="/appointments", tags=["Booking & Scheduling"])


# ── Availability Management (Professional) ────────────────────

@router.post(
    "/availability",
    response_model=WeeklyScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Set weekly availability (Professional).",
)
async def set_availability(
    payload: SetAvailabilityRequest,
    user: User = Depends(require_role("professional")),
    db: AsyncSession = Depends(get_db),
) -> WeeklyScheduleResponse:
    """
    Replace the professional's entire weekly schedule.
    Existing availability is wiped and replaced (idempotent).
    """
    return await BookingService.set_availability(db, user, payload)


@router.get(
    "/availability/{professional_id}",
    response_model=WeeklyScheduleResponse,
    summary="Get a professional's weekly schedule.",
)
async def get_availability(
    professional_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> WeeklyScheduleResponse:
    """Public — view when a professional is generally available."""
    return await BookingService.get_availability(db, professional_id)


@router.get(
    "/slots/{professional_id}",
    response_model=AvailableSlotsResponse,
    summary="Get bookable time slots for a specific date.",
)
async def get_available_slots(
    professional_id: UUID,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db),
) -> AvailableSlotsResponse:
    """
    Public — compute concrete bookable slots for a given date.
    Already-booked slots are marked `is_available: false`.
    """
    return await BookingService.get_available_slots(db, professional_id, date)


# ── Appointment Booking (Patient) ──────────────────────────────

@router.post(
    "/book",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book an appointment (Patient).",
)
async def book_appointment(
    payload: BookAppointmentRequest,
    user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """
    3-gate validation:
      1. Time sanity (not in past, end > start).
      2. Slot within professional's availability window.
      3. No overlap with existing bookings.

    Creates a PENDING appointment on success.
    """
    return await BookingService.book_appointment(db, user, payload)


# ── Status Management ──────────────────────────────────────────

@router.patch(
    "/{appointment_id}/status",
    response_model=AppointmentResponse,
    summary="Update appointment status.",
)
async def update_appointment_status(
    appointment_id: UUID,
    payload: UpdateStatusRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentResponse:
    """
    State machine transitions:
      - **Professional**: PENDING → CONFIRMED/DECLINED, CONFIRMED → COMPLETED
      - **Patient**: PENDING/CONFIRMED → CANCELLED
    """
    return await BookingService.update_status(db, user, appointment_id, payload.status)


# ── Appointment Listing ───────────────────────────────────────

@router.get(
    "",
    response_model=AppointmentListResponse,
    summary="List your appointments.",
)
async def list_appointments(
    role: str | None = Query(default=None, pattern=r"^(patient|professional)$"),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern=r"^(pending|confirmed|declined|cancelled|completed)$",
    ),
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentListResponse:
    """List appointments where the current user is patient or professional."""
    return await BookingService.list_appointments(db, user, role, status_filter)
