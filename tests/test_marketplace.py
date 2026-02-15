"""
Tests — Marketplace Agent (Profiles, Search, Admin Verification).
"""

import pytest
from httpx import AsyncClient

from api.identity.models import User


# ═══════════════════════════════════════════════════════════════
# PROFILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

class TestProfileManagement:
    """Test professional profile CRUD."""

    async def test_create_profile_as_professional(
        self,
        client: AsyncClient,
        professional_user: User,
        professional_headers: dict,
    ):
        """Professional should be able to create a profile."""
        resp = await client.post(
            "/api/v1/professionals/profile",
            headers=professional_headers,
            json={
                "specialty": "Cardiology",
                "license_number": "MED-2024-001",
                "bio": "Heart specialist.",
                "years_of_experience": 10,
                "consultation_fee": 15000.0,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["specialty"] == "Cardiology"
        assert data["is_verified"] is False  # Requires admin

    async def test_create_profile_as_patient_forbidden(
        self,
        client: AsyncClient,
        patient_headers: dict,
    ):
        """Patient should NOT be able to create a professional profile."""
        resp = await client.post(
            "/api/v1/professionals/profile",
            headers=patient_headers,
            json={
                "specialty": "Fake",
                "license_number": "FAKE-001",
            },
        )
        assert resp.status_code == 403

    async def test_create_duplicate_profile(
        self,
        client: AsyncClient,
        professional_user: User,
        professional_headers: dict,
    ):
        """Second profile creation should return 409."""
        payload = {
            "specialty": "Cardiology",
            "license_number": "MED-2024-001",
        }
        await client.post(
            "/api/v1/professionals/profile",
            headers=professional_headers,
            json=payload,
        )
        resp = await client.post(
            "/api/v1/professionals/profile",
            headers=professional_headers,
            json=payload,
        )
        assert resp.status_code == 409

    async def test_update_profile(
        self,
        client: AsyncClient,
        professional_user: User,
        professional_headers: dict,
    ):
        """Professional should be able to partially update their profile."""
        await client.post(
            "/api/v1/professionals/profile",
            headers=professional_headers,
            json={"specialty": "Cardiology", "license_number": "MED-001"},
        )
        resp = await client.patch(
            "/api/v1/professionals/profile",
            headers=professional_headers,
            json={"bio": "Updated bio with more details."},
        )
        assert resp.status_code == 200
        assert resp.json()["bio"] == "Updated bio with more details."


# ═══════════════════════════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════════════════════════

class TestSearch:
    """Test professional search (public endpoint)."""

    async def test_search_returns_only_verified(
        self,
        client: AsyncClient,
        verified_professional: User,  # is_verified=True
    ):
        """Search should only return verified professionals."""
        resp = await client.get("/api/v1/professionals/search")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for result in data["results"]:
            assert result["is_verified"] is True

    async def test_search_by_specialty(
        self,
        client: AsyncClient,
        verified_professional: User,
    ):
        """Search with specialty filter should work."""
        resp = await client.get(
            "/api/v1/professionals/search",
            params={"q": "Cardiology"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_search_no_results(self, client: AsyncClient):
        """Search for nonexistent specialty should return empty."""
        resp = await client.get(
            "/api/v1/professionals/search",
            params={"q": "Xenobiology"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_search_no_auth_required(self, client: AsyncClient):
        """Search endpoint should be public (no auth required)."""
        resp = await client.get("/api/v1/professionals/search")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════
# ADMIN VERIFICATION
# ═══════════════════════════════════════════════════════════════

class TestAdminVerification:
    """Test admin professional verification."""

    async def test_verify_as_patient_forbidden(
        self,
        client: AsyncClient,
        patient_headers: dict,
    ):
        """Patient should NOT be able to verify professionals."""
        import uuid
        resp = await client.patch(
            f"/api/v1/admin/verify-professional/{uuid.uuid4()}",
            headers=patient_headers,
            json={"is_verified": True},
        )
        assert resp.status_code == 403

    async def test_verify_as_professional_forbidden(
        self,
        client: AsyncClient,
        professional_headers: dict,
    ):
        """Professional should NOT be able to verify themselves."""
        import uuid
        resp = await client.patch(
            f"/api/v1/admin/verify-professional/{uuid.uuid4()}",
            headers=professional_headers,
            json={"is_verified": True},
        )
        assert resp.status_code == 403
