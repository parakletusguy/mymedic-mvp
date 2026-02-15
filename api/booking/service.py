"""
Booking Domain — Service Layer.

Core responsibility: ZERO calendar conflicts.

Every booking request goes through a strict 3-gate validation:
  1. Time Sanity  — end > start, not in the past.
  2. Availability — the requested window falls within the professional's schedule.
  3. Conflict     — no existing PENDING/CONFIRMED appointment overlaps.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import (
    Appointment,
    AppointmentStatus,
    Availability,
)
from api.booking.schemas import (
    AppointmentListResponse,
    AppointmentResponse,
    AvailabilityResponse,
    AvailableSlotsResponse,
    BookAppointmentRequest,
    SetAvailabilityRequest,
    TimeSlot,
    WeeklyScheduleResponse,
)
from api.identity.models import User


class BookingService:
    """Stateless service — receives an async session per call."""

    # ═══════════════════════════════════════════════════════════
    # AVAILABILITY
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def set_availability(
        db: AsyncSession,
        professional: User,
        payload: SetAvailabilityRequest,
    ) -> WeeklyScheduleResponse:
        """
        Replace the professional's weekly schedule with the provided slots.

        This is an idempotent "set" — existing availability for this
        professional is wiped and replaced.
        """
        # Validate each slot
        for slot in payload.slots:
            if slot.end_hour <= slot.start_hour:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"end_hour ({slot.end_hour}) must be > start_hour ({slot.start_hour}).",
                )

        # Delete existing schedule
        await db.execute(
            delete(Availability).where(
                Availability.professional_id == professional.id
            )
        )

        # Insert new slots
        new_rows = []
        for slot in payload.slots:
            row = Availability(
                professional_id=professional.id,
                day_of_week=slot.day_of_week,
                start_hour=slot.start_hour,
                end_hour=slot.end_hour,
                slot_duration_min=slot.slot_duration_min,
            )
            db.add(row)
            new_rows.append(row)

        await db.flush()

        return WeeklyScheduleResponse(
            professional_id=professional.id,
            slots=[AvailabilityResponse.model_validate(r) for r in new_rows],
        )

    @staticmethod
    async def get_availability(
        db: AsyncSession,
        professional_id: UUID,
    ) -> WeeklyScheduleResponse:
        """Get the full weekly schedule for a professional."""
        result = await db.execute(
            select(Availability)
            .where(Availability.professional_id == professional_id)
            .order_by(Availability.day_of_week, Availability.start_hour)
        )
        rows = result.scalars().all()

        return WeeklyScheduleResponse(
            professional_id=professional_id,
            slots=[AvailabilityResponse.model_validate(r) for r in rows],
        )

    @staticmethod
    async def get_available_slots(
        db: AsyncSession,
        professional_id: UUID,
        date_str: str,
    ) -> AvailableSlotsResponse:
        """
        Compute bookable time slots for a professional on a specific date.

        Steps:
          1. Parse the date, determine day_of_week.
          2. Fetch availability windows for that weekday.
          3. Generate concrete slots (start_time, end_time).
          4. Subtract already-booked slots (PENDING or CONFIRMED).
        """
        from datetime import date as date_type

        try:
            target_date = date_type.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid date format. Use YYYY-MM-DD.",
            )

        # Reject past dates
        today = datetime.now(timezone.utc).date()
        if target_date < today:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot query availability for past dates.",
            )

        day_of_week = target_date.isoweekday()  # 1=Mon … 7=Sun

        # Fetch availability for this weekday
        result = await db.execute(
            select(Availability).where(
                Availability.professional_id == professional_id,
                Availability.day_of_week == day_of_week,
            )
        )
        availability_rows = result.scalars().all()

        if not availability_rows:
            return AvailableSlotsResponse(
                professional_id=professional_id,
                date=date_str,
                slots=[],
            )

        # Generate concrete time slots
        all_slots: list[TimeSlot] = []
        for avail in availability_rows:
            current_hour = avail.start_hour
            current_min = 0
            while True:
                slot_start = datetime(
                    target_date.year, target_date.month, target_date.day,
                    current_hour, current_min,
                    tzinfo=timezone.utc,
                )
                slot_end = slot_start + timedelta(minutes=avail.slot_duration_min)

                # Don't exceed the window
                window_end = datetime(
                    target_date.year, target_date.month, target_date.day,
                    avail.end_hour, 0,
                    tzinfo=timezone.utc,
                )
                if slot_end > window_end:
                    break

                all_slots.append(TimeSlot(
                    start_time=slot_start,
                    end_time=slot_end,
                ))

                # Advance
                next_time = slot_start + timedelta(minutes=avail.slot_duration_min)
                current_hour = next_time.hour
                current_min = next_time.minute

        # Fetch existing appointments for this date (PENDING or CONFIRMED)
        day_start = datetime(
            target_date.year, target_date.month, target_date.day,
            0, 0, tzinfo=timezone.utc,
        )
        day_end = day_start + timedelta(days=1)

        booked_result = await db.execute(
            select(Appointment).where(
                Appointment.professional_id == professional_id,
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.status.in_([
                    AppointmentStatus.PENDING,
                    AppointmentStatus.CONFIRMED,
                ]),
            )
        )
        booked = booked_result.scalars().all()

        # Mark booked slots as unavailable
        for slot in all_slots:
            for appt in booked:
                if _overlaps(slot.start_time, slot.end_time, appt.start_time, appt.end_time):
                    slot.is_available = False
                    break

        return AvailableSlotsResponse(
            professional_id=professional_id,
            date=date_str,
            slots=all_slots,
        )

    # ═══════════════════════════════════════════════════════════
    # APPOINTMENT BOOKING
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def book_appointment(
        db: AsyncSession,
        patient: User,
        payload: BookAppointmentRequest,
    ) -> AppointmentResponse:
        """
        Book an appointment. Enforces 3-gate validation:
          1. Time sanity (end > start, not in past).
          2. Falls within professional's availability window.
          3. No overlap with existing PENDING/CONFIRMED appointments.
        """

        # ── Gate 1: Time Sanity ────────────────────────────────
        now = datetime.now(timezone.utc)
        if payload.start_time <= now:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot book appointments in the past.",
            )
        if payload.end_time <= payload.start_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_time must be after start_time.",
            )
        if patient.id == payload.professional_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot book an appointment with yourself.",
            )

        # ── Gate 2: Availability Window ────────────────────────
        target_day = payload.start_time.isoweekday()
        target_start_hour = payload.start_time.hour
        target_end_hour = payload.end_time.hour
        if payload.end_time.minute > 0:
            target_end_hour += 1  # Round up to cover partial hours

        avail_result = await db.execute(
            select(Availability).where(
                Availability.professional_id == payload.professional_id,
                Availability.day_of_week == target_day,
                Availability.start_hour <= target_start_hour,
                Availability.end_hour >= target_end_hour,
            )
        )
        if not avail_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Requested time is outside the professional's availability.",
            )

        # ── Gate 3: Conflict Check (CRITICAL) ─────────────────
        # Overlap condition: existing.start < new.end AND existing.end > new.start
        conflict_result = await db.execute(
            select(func.count()).where(
                Appointment.professional_id == payload.professional_id,
                Appointment.status.in_([
                    AppointmentStatus.PENDING,
                    AppointmentStatus.CONFIRMED,
                ]),
                Appointment.start_time < payload.end_time,
                Appointment.end_time > payload.start_time,
            )
        )
        conflict_count = conflict_result.scalar() or 0

        if conflict_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time slot conflict. This slot is already booked.",
            )

        # ── All gates passed — create appointment ──────────────
        appointment = Appointment(
            patient_id=patient.id,
            professional_id=payload.professional_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            status=AppointmentStatus.PENDING,
            notes=payload.notes,
        )
        db.add(appointment)
        await db.flush()

        return AppointmentResponse.model_validate(appointment)

    # ═══════════════════════════════════════════════════════════
    # STATUS MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def update_status(
        db: AsyncSession,
        user: User,
        appointment_id: UUID,
        new_status: str,
    ) -> AppointmentResponse:
        """
        Update appointment status with state-machine validation.

        Allowed transitions:
          - Professional: PENDING → CONFIRMED | DECLINED
          - Professional: CONFIRMED → COMPLETED
          - Patient: PENDING → CANCELLED
          - Patient: CONFIRMED → CANCELLED
        """
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appt = result.scalar_one_or_none()
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        target = AppointmentStatus(new_status)
        current = appt.status

        # Determine who's acting
        is_professional = user.id == appt.professional_id
        is_patient = user.id == appt.patient_id

        if not is_professional and not is_patient:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a party to this appointment.",
            )

        # Validate transitions
        valid = False
        if is_professional:
            if current == AppointmentStatus.PENDING and target in (
                AppointmentStatus.CONFIRMED, AppointmentStatus.DECLINED
            ):
                valid = True
            elif current == AppointmentStatus.CONFIRMED and target == AppointmentStatus.COMPLETED:
                valid = True
        if is_patient:
            if current in (AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED) and \
               target == AppointmentStatus.CANCELLED:
                valid = True

        if not valid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid transition: {current.value} → {target.value} "
                       f"(by {'professional' if is_professional else 'patient'}).",
            )

        appt.status = target
        await db.flush()

        return AppointmentResponse.model_validate(appt)

    # ═══════════════════════════════════════════════════════════
    # LISTING
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def list_appointments(
        db: AsyncSession,
        user: User,
        role_filter: str | None = None,
        status_filter: str | None = None,
    ) -> AppointmentListResponse:
        """
        List appointments for the current user (as patient or professional).
        """
        base = select(Appointment)

        if role_filter == "patient":
            base = base.where(Appointment.patient_id == user.id)
        elif role_filter == "professional":
            base = base.where(Appointment.professional_id == user.id)
        else:
            # Return all where user is either party
            base = base.where(
                or_(
                    Appointment.patient_id == user.id,
                    Appointment.professional_id == user.id,
                )
            )

        if status_filter:
            base = base.where(Appointment.status == AppointmentStatus(status_filter))

        base = base.order_by(Appointment.start_time.desc())

        result = await db.execute(base)
        rows = result.scalars().all()

        return AppointmentListResponse(
            appointments=[AppointmentResponse.model_validate(r) for r in rows],
            total=len(rows),
        )


# ── Helpers ────────────────────────────────────────────────────

def _overlaps(
    a_start: datetime, a_end: datetime,
    b_start: datetime, b_end: datetime,
) -> bool:
    """Return True if two time ranges overlap."""
    return a_start < b_end and a_end > b_start
