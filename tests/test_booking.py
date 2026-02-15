"""
Tests — Booking Agent (Availability, Booking, Conflict Check, Status).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Appointment, AppointmentStatus, Availability
from api.identity.models import User
from tests.conftest import auth_headers


# ═══════════════════════════════════════════════════════════════
# AVAILABILITY
# ═══════════════════════════════════════════════════════════════

class TestAvailability:
    """Test availability management."""

    async def test_set_availability_as_professional(
        self,
        client: AsyncClient,
        professional_headers: dict,
    ):
        """Professional can set their weekly schedule."""
        resp = await client.post(
            "/api/v1/appointments/availability",
            headers=professional_headers,
            json={
                "slots": [
                    {"day_of_week": 1, "start_hour": 9, "end_hour": 17},
                    {"day_of_week": 3, "start_hour": 9, "end_hour": 13},
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["slots"]) == 2

    async def test_set_availability_as_patient_forbidden(
        self,
        client: AsyncClient,
        patient_headers: dict,
    ):
        """Patient should NOT set availability."""
        resp = await client.post(
            "/api/v1/appointments/availability",
            headers=patient_headers,
            json={"slots": [{"day_of_week": 1, "start_hour": 9, "end_hour": 17}]},
        )
        assert resp.status_code == 403

    async def test_get_availability(
        self,
        client: AsyncClient,
        professional_user: User,
        professional_headers: dict,
    ):
        """Public endpoint — get a professional's schedule."""
        # Set first
        await client.post(
            "/api/v1/appointments/availability",
            headers=professional_headers,
            json={"slots": [{"day_of_week": 1, "start_hour": 9, "end_hour": 17}]},
        )
        resp = await client.get(
            f"/api/v1/appointments/availability/{professional_user.id}"
        )
        assert resp.status_code == 200
        assert len(resp.json()["slots"]) == 1


# ═══════════════════════════════════════════════════════════════
# BOOKING
# ═══════════════════════════════════════════════════════════════

class TestBooking:
    """Test appointment booking with conflict checks."""

    async def _setup_availability(
        self,
        db_session: AsyncSession,
        professional_id: uuid.UUID,
    ):
        """Insert availability for all weekdays 9-17."""
        for day in range(1, 6):  # Mon-Fri
            avail = Availability(
                professional_id=professional_id,
                day_of_week=day,
                start_hour=9,
                end_hour=17,
                slot_duration_min=30,
            )
            db_session.add(avail)
        await db_session.commit()

    async def test_book_appointment_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Valid booking should return 201 PENDING."""
        await self._setup_availability(db_session, verified_professional.id)

        # Find the next Monday
        now = datetime.now(timezone.utc)
        days_ahead = (7 - now.weekday()) % 7 or 7  # Next Monday
        next_monday = now + timedelta(days=days_ahead)
        start = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        resp = await client.post(
            "/api/v1/appointments/book",
            headers=patient_headers,
            json={
                "professional_id": str(verified_professional.id),
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    async def test_book_in_the_past(
        self,
        client: AsyncClient,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Booking in the past should return 422."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        resp = await client.post(
            "/api/v1/appointments/book",
            headers=patient_headers,
            json={
                "professional_id": str(verified_professional.id),
                "start_time": past.isoformat(),
                "end_time": (past + timedelta(minutes=30)).isoformat(),
            },
        )
        assert resp.status_code == 422

    async def test_double_booking_conflict(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Booking the same slot twice should return 409 (conflict)."""
        await self._setup_availability(db_session, verified_professional.id)

        now = datetime.now(timezone.utc)
        days_ahead = (7 - now.weekday()) % 7 or 7
        next_monday = now + timedelta(days=days_ahead)
        start = next_monday.replace(hour=11, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        payload = {
            "professional_id": str(verified_professional.id),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        }

        # First booking — should succeed
        resp1 = await client.post(
            "/api/v1/appointments/book",
            headers=patient_headers,
            json=payload,
        )
        assert resp1.status_code == 201

        # Second booking — same slot → 409
        resp2 = await client.post(
            "/api/v1/appointments/book",
            headers=patient_headers,
            json=payload,
        )
        assert resp2.status_code == 409

    async def test_book_as_professional_forbidden(
        self,
        client: AsyncClient,
        professional_headers: dict,
    ):
        """Professional should NOT book (only patients can)."""
        resp = await client.post(
            "/api/v1/appointments/book",
            headers=professional_headers,
            json={
                "professional_id": str(uuid.uuid4()),
                "start_time": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "end_time": (datetime.now(timezone.utc) + timedelta(days=1, minutes=30)).isoformat(),
            },
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# STATUS MANAGEMENT
# ═══════════════════════════════════════════════════════════════

class TestStatusManagement:
    """Test appointment status transitions."""

    async def test_professional_confirms(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        professional_headers: dict,
        db_session: AsyncSession,
    ):
        """Professional should be able to complete a confirmed appointment."""
        resp = await client.patch(
            f"/api/v1/appointments/{confirmed_appointment.id}/status",
            headers=professional_headers,
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    async def test_patient_cancels(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_headers: dict,
    ):
        """Patient should be able to cancel a confirmed appointment."""
        resp = await client.patch(
            f"/api/v1/appointments/{confirmed_appointment.id}/status",
            headers=patient_headers,
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_invalid_transition(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_headers: dict,
    ):
        """Patient should NOT be able to decline (only professional can)."""
        resp = await client.patch(
            f"/api/v1/appointments/{confirmed_appointment.id}/status",
            headers=patient_headers,
            json={"status": "declined"},
        )
        assert resp.status_code == 422
