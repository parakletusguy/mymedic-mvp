"""
MyMedic QA — Shared Test Fixtures (conftest.py).

Provides:
  - Async SQLite test database (no Postgres dependency for CI).
  - FastAPI TestClient via httpx.AsyncClient.
  - Reusable fixtures: create_user, get_auth_headers,
    create_verified_professional, create_appointment.

Architecture:
  - Each test gets a fresh DB (function-scoped session).
  - App dependency overrides swap the real DB for the test DB.
  - All external services (Paystack) are mocked via the gateway's mock mode.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.core.database import Base, get_db
from api.core.security import create_access_token, hash_password
from api.identity.models import User, UserRole

# ── Test Database ──────────────────────────────────────────────
# In-memory SQLite — fast, isolated, no external dependencies.

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Event Loop ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Override default event loop for session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database Setup / Teardown ─────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh DB session per test."""
    async with TestSessionLocal() as session:
        yield session


# ── Override the app's DB dependency ──────────────────────────

async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── FastAPI Test Client ───────────────────────────────────────

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client pointing at the FastAPI ASGI app."""
    from api.main import app

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════
# REUSABLE FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def patient_user(db_session: AsyncSession) -> User:
    """Create and return a verified patient user."""
    user = User(
        id=uuid.uuid4(),
        email="patient@test.com",
        password_hash=hash_password("Test1234!"),
        role=UserRole.PATIENT,
        is_active=True,
        is_verified=True,
        otp_secret="JBSWY3DPEHPK3PXP",  # Standard test secret
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def professional_user(db_session: AsyncSession) -> User:
    """Create and return a verified professional user."""
    user = User(
        id=uuid.uuid4(),
        email="doctor@test.com",
        password_hash=hash_password("Test1234!"),
        role=UserRole.PROFESSIONAL,
        is_active=True,
        is_verified=True,
        otp_secret="JBSWY3DPEHPK3PXP",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create and return an admin user."""
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        password_hash=hash_password("Admin1234!"),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        otp_secret="JBSWY3DPEHPK3PXP",
    )
    db_session.add(user)
    await db_session.commit()
    return user


def auth_headers(user: User) -> dict:
    """Generate Authorization headers with a valid JWT for the given user."""
    token = create_access_token(user.id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def patient_headers(patient_user: User) -> dict:
    """Auth headers for the patient."""
    return auth_headers(patient_user)


@pytest_asyncio.fixture
async def professional_headers(professional_user: User) -> dict:
    """Auth headers for the professional."""
    return auth_headers(professional_user)


@pytest_asyncio.fixture
async def admin_headers(admin_user: User) -> dict:
    """Auth headers for the admin."""
    return auth_headers(admin_user)


# ── Professional Profile Fixture ──────────────────────────────

@pytest_asyncio.fixture
async def verified_professional(
    db_session: AsyncSession,
    professional_user: User,
) -> User:
    """Create a professional with a verified profile."""
    from api.marketplace.models import ProfessionalProfile

    profile = ProfessionalProfile(
        user_id=professional_user.id,
        specialty="Cardiology",
        sub_specialties="Interventional Cardiology, Heart Failure",
        bio="Board-certified cardiologist with 15 years of experience.",
        license_number="MED-2024-001",
        years_of_experience=15,
        consultation_fee=25000.0,  # ₦25,000
        is_verified=True,
        rating=4.8,
        review_count=47,
    )
    db_session.add(profile)
    await db_session.commit()
    return professional_user


# ── Appointment Fixture ───────────────────────────────────────

@pytest_asyncio.fixture
async def confirmed_appointment(
    db_session: AsyncSession,
    patient_user: User,
    verified_professional: User,
):
    """Create a CONFIRMED appointment between patient and professional."""
    from api.booking.models import Appointment, AppointmentStatus

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    appt = Appointment(
        id=uuid.uuid4(),
        patient_id=patient_user.id,
        professional_id=verified_professional.id,
        start_time=tomorrow.replace(hour=10, minute=0),
        end_time=tomorrow.replace(hour=10, minute=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(appt)
    await db_session.commit()
    return appt
