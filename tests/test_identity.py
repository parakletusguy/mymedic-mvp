"""
Tests — Identity Agent (Registration, Login, 2FA, Token Refresh).
"""

import pytest
from httpx import AsyncClient

from api.identity.models import User


# ═══════════════════════════════════════════════════════════════
# REGISTRATION
# ═══════════════════════════════════════════════════════════════

class TestRegistration:
    """Test the /auth/register endpoint."""

    async def test_register_patient_success(self, client: AsyncClient):
        """Valid registration should return 201 with user data."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newpatient@test.com",
            "password": "Strong1234!",
            "role": "patient",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newpatient@test.com"
        assert "id" in data

    async def test_register_professional_success(self, client: AsyncClient):
        """Professional registration should work."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "newdoc@test.com",
            "password": "Strong1234!",
            "role": "professional",
        })
        assert resp.status_code == 201

    async def test_register_duplicate_email(self, client: AsyncClient):
        """Duplicate email should return 409."""
        payload = {
            "email": "dupe@test.com",
            "password": "Strong1234!",
            "role": "patient",
        }
        await client.post("/api/v1/auth/register", json=payload)
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        """Weak password should return 422."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@test.com",
            "password": "weak",
            "role": "patient",
        })
        assert resp.status_code == 422

    async def test_register_invalid_role(self, client: AsyncClient):
        """Invalid role should return 422."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "badrole@test.com",
            "password": "Strong1234!",
            "role": "superadmin",
        })
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════
# LOGIN (Step 1: Credentials → Interim Token)
# ═══════════════════════════════════════════════════════════════

class TestLogin:
    """Test the /auth/login endpoint."""

    async def test_login_valid_credentials(self, client: AsyncClient):
        """Valid login should return an interim token for 2FA."""
        # Register first
        await client.post("/api/v1/auth/register", json={
            "email": "logintest@test.com",
            "password": "Strong1234!",
            "role": "patient",
        })
        resp = await client.post("/api/v1/auth/login", data={
            "username": "logintest@test.com",
            "password": "Strong1234!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["otp_required"] is True
        assert "interim_token" in data

    async def test_login_wrong_password(self, client: AsyncClient):
        """Wrong password should return 401."""
        await client.post("/api/v1/auth/register", json={
            "email": "wrongpw@test.com",
            "password": "Strong1234!",
            "role": "patient",
        })
        resp = await client.post("/api/v1/auth/login", data={
            "username": "wrongpw@test.com",
            "password": "WrongPassword1!",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Nonexistent user should return 401 (no user enumeration)."""
        resp = await client.post("/api/v1/auth/login", data={
            "username": "ghost@test.com",
            "password": "Strong1234!",
        })
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════
# PROTECTED ROUTES
# ═══════════════════════════════════════════════════════════════

class TestProtectedRoutes:
    """Test auth-protected endpoints."""

    async def test_me_with_valid_token(
        self, client: AsyncClient, patient_user: User, patient_headers: dict,
    ):
        """Authenticated user should get their profile."""
        resp = await client.get("/api/v1/auth/me", headers=patient_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == patient_user.email

    async def test_me_without_token(self, client: AsyncClient):
        """No token should return 401."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, client: AsyncClient):
        """Invalid token should return 401."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
