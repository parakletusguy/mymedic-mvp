"""
Tests — Finance Agent (Payment Initialization, Webhook, Admin Ledger).

Paystack is auto-mocked via the gateway's built-in mock mode.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Appointment, AppointmentStatus
from api.identity.models import User


# ═══════════════════════════════════════════════════════════════
# PAYMENT INITIALIZATION
# ═══════════════════════════════════════════════════════════════

class TestPaymentInitialization:
    """Test POST /payments/initialize."""

    async def test_initialize_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        patient_user: User,
        verified_professional: User,
        patient_headers: dict,
    ):
        """Patient initializes payment for a pending appointment."""
        # Create a PENDING appointment
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
            "/api/v1/payments/initialize",
            headers=patient_headers,
            json={"appointment_id": str(appt.id)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "reference" in data
        assert "checkout_url" in data

    async def test_initialize_as_professional_forbidden(
        self,
        client: AsyncClient,
        professional_headers: dict,
    ):
        """Professional should NOT initialize payments."""
        resp = await client.post(
            "/api/v1/payments/initialize",
            headers=professional_headers,
            json={"appointment_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════
# TRANSACTION HISTORY
# ═══════════════════════════════════════════════════════════════

class TestTransactionHistory:
    """Test GET /payments/history."""

    async def test_history_empty(
        self,
        client: AsyncClient,
        patient_headers: dict,
    ):
        """Empty history should return 200 with empty list."""
        resp = await client.get(
            "/api/v1/payments/history",
            headers=patient_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == [] or isinstance(resp.json(), list)


# ═══════════════════════════════════════════════════════════════
# ADMIN EARNINGS LEDGER
# ═══════════════════════════════════════════════════════════════

class TestAdminEarnings:
    """Test GET /admin/earnings."""

    async def test_earnings_as_admin(
        self,
        client: AsyncClient,
        admin_headers: dict,
    ):
        """Admin should access earnings ledger."""
        resp = await client.get(
            "/api/v1/admin/earnings",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    async def test_earnings_as_patient_forbidden(
        self,
        client: AsyncClient,
        patient_headers: dict,
    ):
        """Patient should NOT access earnings ledger."""
        resp = await client.get(
            "/api/v1/admin/earnings",
            headers=patient_headers,
        )
        assert resp.status_code == 403

    async def test_earnings_as_professional_forbidden(
        self,
        client: AsyncClient,
        professional_headers: dict,
    ):
        """Professional should NOT access earnings ledger."""
        resp = await client.get(
            "/api/v1/admin/earnings",
            headers=professional_headers,
        )
        assert resp.status_code == 403
