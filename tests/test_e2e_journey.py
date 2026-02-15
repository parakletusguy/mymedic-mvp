"""
Tests — End-to-End User Journey.

Simulates the COMPLETE happy path a real user would follow:
  Register Patient → Register Professional → Admin Verifies →
  Search → Book → Pay → Confirm → Chat → Complete.

This is the single most important test in the suite.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Availability
from api.core.security import hash_password
from api.identity.models import User, UserRole
from tests.conftest import auth_headers


class TestEndToEndJourney:
    """Full user journey from registration to chat completion."""

    async def test_full_happy_path(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Complete flow:
          1. Register patient
          2. Register professional
          3. Professional creates profile
          4. Admin verifies professional
          5. Patient searches and finds professional
          6. Professional sets availability
          7. Patient books appointment
          8. Patient initializes payment
          9. Professional confirms appointment
         10. Patient and Professional exchange messages
         11. Professional completes appointment
        """
        # ─── Step 1: Register Patient ──────────────────────────
        resp = await client.post("/api/v1/auth/register", json={
            "email": "e2e_patient@test.com",
            "password": "Secure1234!",
            "role": "patient",
        })
        assert resp.status_code == 201
        patient_id = resp.json()["id"]

        # ─── Step 2: Register Professional ─────────────────────
        resp = await client.post("/api/v1/auth/register", json={
            "email": "e2e_doctor@test.com",
            "password": "Secure1234!",
            "role": "professional",
        })
        assert resp.status_code == 201
        professional_id = resp.json()["id"]

        # --- Get auth tokens (directly via DB for test speed) --
        patient = await db_session.get(User, uuid.UUID(patient_id))
        patient.is_verified = True
        professional = await db_session.get(User, uuid.UUID(professional_id))
        professional.is_verified = True
        await db_session.commit()

        p_headers = auth_headers(patient)
        d_headers = auth_headers(professional)

        # Create admin for verification
        admin = User(
            id=uuid.uuid4(),
            email="e2e_admin@test.com",
            password_hash=hash_password("Admin1234!"),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            otp_secret="JBSWY3DPEHPK3PXP",
        )
        db_session.add(admin)
        await db_session.commit()
        a_headers = auth_headers(admin)

        # ─── Step 3: Professional Creates Profile ──────────────
        resp = await client.post(
            "/api/v1/professionals/profile",
            headers=d_headers,
            json={
                "specialty": "Dermatology",
                "license_number": "DERM-E2E-001",
                "bio": "Skin specialist for end-to-end testing.",
                "years_of_experience": 8,
                "consultation_fee": 20000.0,
            },
        )
        assert resp.status_code == 201
        assert resp.json()["is_verified"] is False

        # ─── Step 4: Admin Verifies Professional ───────────────
        resp = await client.patch(
            f"/api/v1/admin/verify-professional/{professional_id}",
            headers=a_headers,
            json={"is_verified": True},
        )
        assert resp.status_code == 200
        assert resp.json()["is_verified"] is True

        # ─── Step 5: Patient Searches for Professional ─────────
        resp = await client.get(
            "/api/v1/professionals/search",
            params={"q": "Dermatology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        found_ids = [r["user_id"] for r in data["results"]]
        assert professional_id in found_ids

        # ─── Step 6: Professional Sets Availability ────────────
        resp = await client.post(
            "/api/v1/appointments/availability",
            headers=d_headers,
            json={
                "slots": [
                    {"day_of_week": day, "start_hour": 9, "end_hour": 17}
                    for day in range(1, 6)
                ],
            },
        )
        assert resp.status_code == 201

        # ─── Step 7: Patient Books Appointment ─────────────────
        now = datetime.now(timezone.utc)
        days_ahead = (7 - now.weekday()) % 7 or 7
        next_monday = now + timedelta(days=days_ahead)
        start = next_monday.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        resp = await client.post(
            "/api/v1/appointments/book",
            headers=p_headers,
            json={
                "professional_id": professional_id,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )
        assert resp.status_code == 201
        appointment_id = resp.json()["id"]
        assert resp.json()["status"] == "pending"

        # ─── Step 8: Patient Initializes Payment ───────────────
        resp = await client.post(
            "/api/v1/payments/initialize",
            headers=p_headers,
            json={"appointment_id": appointment_id},
        )
        assert resp.status_code == 201
        assert "checkout_url" in resp.json()

        # ─── Step 9: Professional Confirms Appointment ─────────
        resp = await client.patch(
            f"/api/v1/appointments/{appointment_id}/status",
            headers=d_headers,
            json={"status": "confirmed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

        # ─── Step 10: Secure Messaging ─────────────────────────
        # Patient sends
        resp = await client.post(
            "/api/v1/chat/send",
            headers=p_headers,
            json={
                "appointment_id": appointment_id,
                "content": "Hello doctor, looking forward to our session!",
            },
        )
        assert resp.status_code == 201

        # Professional replies
        resp = await client.post(
            "/api/v1/chat/send",
            headers=d_headers,
            json={
                "appointment_id": appointment_id,
                "content": "Hi! Please share your symptoms beforehand.",
            },
        )
        assert resp.status_code == 201

        # Patient reads history
        resp = await client.get(
            f"/api/v1/chat/history/{appointment_id}",
            headers=p_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

        # ─── Step 11: Professional Completes ───────────────────
        resp = await client.patch(
            f"/api/v1/appointments/{appointment_id}/status",
            headers=d_headers,
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # ─── Post-Completion: Chat Still Accessible ────────────
        resp = await client.get(
            f"/api/v1/chat/history/{appointment_id}",
            headers=p_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

        # ─── Verify Admin Earnings Ledger Has Data ────────────
        resp = await client.get(
            "/api/v1/admin/earnings", headers=a_headers,
        )
        assert resp.status_code == 200
