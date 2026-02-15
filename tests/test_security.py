"""
Tests — Security & Negative Tests (Penetration-Style).

Validates that the system correctly rejects unauthorized access
across all agent boundaries. These are the tests that "break"
the system before users do.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Appointment, AppointmentStatus
from api.core.security import hash_password
from api.identity.models import User, UserRole
from tests.conftest import auth_headers


class TestRBACPenetration:
    """Test that role-based access control cannot be bypassed."""

    # ── Patient tries Professional-only routes ────────────────

    async def test_patient_cannot_set_availability(
        self, client: AsyncClient, patient_headers: dict,
    ):
        resp = await client.post(
            "/api/v1/appointments/availability",
            headers=patient_headers,
            json={"slots": [{"day_of_week": 1, "start_hour": 9, "end_hour": 17}]},
        )
        assert resp.status_code == 403

    async def test_patient_cannot_create_professional_profile(
        self, client: AsyncClient, patient_headers: dict,
    ):
        resp = await client.post(
            "/api/v1/professionals/profile",
            headers=patient_headers,
            json={"specialty": "Hacking", "license_number": "FAKE"},
        )
        assert resp.status_code == 403

    # ── Professional tries Patient-only routes ────────────────

    async def test_professional_cannot_book(
        self, client: AsyncClient, professional_headers: dict,
    ):
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

    async def test_professional_cannot_initialize_payment(
        self, client: AsyncClient, professional_headers: dict,
    ):
        resp = await client.post(
            "/api/v1/payments/initialize",
            headers=professional_headers,
            json={"appointment_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 403

    # ── Non-Admin tries Admin-only routes ─────────────────────

    async def test_patient_cannot_verify_professional(
        self, client: AsyncClient, patient_headers: dict,
    ):
        resp = await client.patch(
            f"/api/v1/admin/verify-professional/{uuid.uuid4()}",
            headers=patient_headers,
            json={"is_verified": True},
        )
        assert resp.status_code == 403

    async def test_professional_cannot_verify_professional(
        self, client: AsyncClient, professional_headers: dict,
    ):
        resp = await client.patch(
            f"/api/v1/admin/verify-professional/{uuid.uuid4()}",
            headers=professional_headers,
            json={"is_verified": True},
        )
        assert resp.status_code == 403

    async def test_patient_cannot_access_admin_earnings(
        self, client: AsyncClient, patient_headers: dict,
    ):
        resp = await client.get(
            "/api/v1/admin/earnings", headers=patient_headers,
        )
        assert resp.status_code == 403

    async def test_professional_cannot_access_admin_earnings(
        self, client: AsyncClient, professional_headers: dict,
    ):
        resp = await client.get(
            "/api/v1/admin/earnings", headers=professional_headers,
        )
        assert resp.status_code == 403


class TestChatSecurityPenetration:
    """Test that messaging boundaries cannot be bypassed."""

    async def test_unlinked_user_cannot_read_chat(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        confirmed_appointment: Appointment,
    ):
        """Third party should not read someone else's chat history."""
        intruder = User(
            id=uuid.uuid4(),
            email="intruder@evil.com",
            password_hash=hash_password("Evil1234!"),
            role=UserRole.PATIENT,
            is_active=True,
            is_verified=True,
            otp_secret="JBSWY3DPEHPK3PXP",
        )
        db_session.add(intruder)
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/chat/history/{confirmed_appointment.id}",
            headers=auth_headers(intruder),
        )
        assert resp.status_code == 403

    async def test_unlinked_user_cannot_send_message(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        confirmed_appointment: Appointment,
    ):
        """Third party should not send messages to other's appointment."""
        intruder = User(
            id=uuid.uuid4(),
            email="spy@evil.com",
            password_hash=hash_password("Evil1234!"),
            role=UserRole.PATIENT,
            is_active=True,
            is_verified=True,
            otp_secret="JBSWY3DPEHPK3PXP",
        )
        db_session.add(intruder)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/chat/send",
            headers=auth_headers(intruder),
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "I'm eavesdropping!",
            },
        )
        assert resp.status_code == 403

    async def test_chat_blocked_before_confirmation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Messaging should be blocked when appointment is PENDING."""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=2)
        pending_appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            professional_id=verified_professional.id,
            start_time=tomorrow.replace(hour=15, minute=0),
            end_time=tomorrow.replace(hour=15, minute=30),
            status=AppointmentStatus.PENDING,
        )
        db_session.add(pending_appt)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(pending_appt.id),
                "content": "Can we start early?",
            },
        )
        assert resp.status_code == 403
        assert "CONFIRMED" in resp.json()["detail"]


class TestTokenSecurity:
    """Test authentication token edge cases."""

    async def test_expired_token_rejected(self, client: AsyncClient):
        """An expired JWT should be rejected."""
        from api.core.security import create_access_token

        # Create a token with -1 minute expiry (already expired)
        user_id = uuid.uuid4()
        token = create_access_token(user_id, "patient", expires_delta=timedelta(minutes=-1))

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401

    async def test_malformed_token_rejected(self, client: AsyncClient):
        """A malformed JWT should be rejected."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert resp.status_code == 401

    async def test_no_auth_header_rejected(self, client: AsyncClient):
        """Missing Authorization header should return 401."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_wrong_scheme_rejected(self, client: AsyncClient):
        """Using 'Basic' instead of 'Bearer' should fail."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code in (401, 403)


class TestBookingConflicts:
    """Test race condition / conflict handling."""

    async def test_overlapping_time_range_rejected(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Overlapping (not identical) booking should also be rejected."""
        from api.booking.models import Availability

        for day in range(1, 6):
            avail = Availability(
                professional_id=verified_professional.id,
                day_of_week=day,
                start_hour=9,
                end_hour=17,
                slot_duration_min=30,
            )
            db_session.add(avail)
        await db_session.commit()

        now = datetime.now(timezone.utc)
        days_ahead = (7 - now.weekday()) % 7 or 7
        next_monday = now + timedelta(days=days_ahead)

        # Book 10:00 - 10:30
        start1 = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
        end1 = start1 + timedelta(minutes=30)

        resp1 = await client.post(
            "/api/v1/appointments/book",
            headers=patient_headers,
            json={
                "professional_id": str(verified_professional.id),
                "start_time": start1.isoformat(),
                "end_time": end1.isoformat(),
            },
        )
        assert resp1.status_code == 201

        # Attempt 10:15 - 10:45 (overlaps by 15 min)
        start2 = next_monday.replace(hour=10, minute=15, second=0, microsecond=0)
        end2 = start2 + timedelta(minutes=30)

        resp2 = await client.post(
            "/api/v1/appointments/book",
            headers=patient_headers,
            json={
                "professional_id": str(verified_professional.id),
                "start_time": start2.isoformat(),
                "end_time": end2.isoformat(),
            },
        )
        assert resp2.status_code == 409
