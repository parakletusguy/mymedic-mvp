"""
Tests — Comms Agent (Gatekeeper, Send, Chat History, Read Receipts).

Validates that messaging is strictly appointment-gated.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Appointment, AppointmentStatus
from api.identity.models import User, UserRole
from tests.conftest import auth_headers


# ═══════════════════════════════════════════════════════════════
# GATEKEEPER — THE CORE SECURITY BOUNDARY
# ═══════════════════════════════════════════════════════════════

class TestGatekeeper:
    """Validate that the gatekeeper blocks unauthorized messaging."""

    async def test_send_without_appointment_404(
        self,
        client: AsyncClient,
        patient_headers: dict,
    ):
        """Sending with a fake appointment ID should return 404."""
        resp = await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(uuid.uuid4()),
                "content": "Hello doc!",
            },
        )
        assert resp.status_code == 404

    async def test_send_to_pending_appointment_403(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Messaging a PENDING (unconfirmed) appointment should return 403."""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            professional_id=verified_professional.id,
            start_time=tomorrow.replace(hour=10, minute=0),
            end_time=tomorrow.replace(hour=10, minute=30),
            status=AppointmentStatus.PENDING,
        )
        db_session.add(appt)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(appt.id),
                "content": "Can we chat?",
            },
        )
        assert resp.status_code == 403
        assert "CONFIRMED" in resp.json()["detail"]

    async def test_send_to_cancelled_appointment_403(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Messaging a CANCELLED appointment should return 403."""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        appt = Appointment(
            id=uuid.uuid4(),
            patient_id=patient_user.id,
            professional_id=verified_professional.id,
            start_time=tomorrow.replace(hour=14, minute=0),
            end_time=tomorrow.replace(hour=14, minute=30),
            status=AppointmentStatus.CANCELLED,
        )
        db_session.add(appt)
        await db_session.commit()

        resp = await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(appt.id),
                "content": "Why was it cancelled?",
            },
        )
        assert resp.status_code == 403

    async def test_unrelated_user_forbidden(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        confirmed_appointment: Appointment,
    ):
        """A third-party user should NOT access someone else's chat."""
        from api.core.security import hash_password

        stranger = User(
            id=uuid.uuid4(),
            email="stranger@test.com",
            password_hash=hash_password("Test1234!"),
            role=UserRole.PATIENT,
            is_active=True,
            is_verified=True,
            otp_secret="JBSWY3DPEHPK3PXP",
        )
        db_session.add(stranger)
        await db_session.commit()

        stranger_headers = auth_headers(stranger)

        # Try to send a message
        resp = await client.post(
            "/api/v1/chat/send",
            headers=stranger_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "I shouldn't be here.",
            },
        )
        assert resp.status_code == 403

        # Try to read history
        resp = await client.get(
            f"/api/v1/chat/history/{confirmed_appointment.id}",
            headers=stranger_headers,
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# SEND & RECEIVE — HAPPY PATH
# ═══════════════════════════════════════════════════════════════

class TestSendReceive:
    """Test valid message flow between connected parties."""

    async def test_patient_sends_message(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Patient can send a message within a confirmed appointment."""
        resp = await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "Hello doctor, I have a question.",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sender_id"] == str(patient_user.id)
        assert data["receiver_id"] == str(verified_professional.id)
        assert data["content"] == "Hello doctor, I have a question."
        assert data["is_read"] is False

    async def test_professional_sends_reply(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_user: User,
        verified_professional: User,
        professional_headers: dict,
    ):
        """Professional can reply within the same appointment."""
        resp = await client.post(
            "/api/v1/chat/send",
            headers=professional_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "Hi! How can I help you today?",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sender_id"] == str(verified_professional.id)
        assert data["receiver_id"] == str(patient_user.id)

    async def test_chat_history_chronological(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_headers: dict,
        professional_headers: dict,
    ):
        """Chat history should be in chronological order."""
        # Send two messages
        await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "Message 1",
            },
        )
        await client.post(
            "/api/v1/chat/send",
            headers=professional_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "Message 2",
            },
        )

        # Fetch history
        resp = await client.get(
            f"/api/v1/chat/history/{confirmed_appointment.id}",
            headers=patient_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["messages"][0]["content"] == "Message 1"
        assert data["messages"][1]["content"] == "Message 2"


# ═══════════════════════════════════════════════════════════════
# UNREAD & READ RECEIPTS
# ═══════════════════════════════════════════════════════════════

class TestReadReceipts:
    """Test unread count and mark-as-read."""

    async def test_unread_count(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_headers: dict,
        professional_headers: dict,
    ):
        """Unread count should reflect unread messages for receiver."""
        # Patient sends a message → professional has 1 unread
        await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "Unread test message",
            },
        )

        resp = await client.get(
            "/api/v1/chat/unread",
            headers=professional_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["unread_count"] >= 1

    async def test_mark_as_read(
        self,
        client: AsyncClient,
        confirmed_appointment: Appointment,
        patient_headers: dict,
        professional_headers: dict,
    ):
        """Marking messages as read should reduce unread count."""
        # Patient sends
        await client.post(
            "/api/v1/chat/send",
            headers=patient_headers,
            json={
                "appointment_id": str(confirmed_appointment.id),
                "content": "Please read me",
            },
        )

        # Professional marks as read
        resp = await client.post(
            "/api/v1/chat/read",
            headers=professional_headers,
            json={"appointment_id": str(confirmed_appointment.id)},
        )
        assert resp.status_code == 200
        assert resp.json()["marked_count"] >= 1

        # Check unread is now 0
        resp = await client.get(
            "/api/v1/chat/unread",
            headers=professional_headers,
        )
        assert resp.json()["unread_count"] == 0
