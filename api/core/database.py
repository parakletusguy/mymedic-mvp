"""
MyMedic Core — Async Database Engine & Session Factory.

Uses SQLAlchemy 2.0 async with asyncpg driver.
Every request gets an isolated async session via dependency injection.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from api.core.config import settings

# ── Engine ─────────────────────────────────────────────────────
engine = create_async_engine(
    settings.sqlalchemy_database_url,
    echo=settings.debug,
    pool_pre_ping=True,       # detect broken connections
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Declarative Base ───────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared declarative base for all domain models."""
    pass


# ── Dependency: per-request session ────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Yield a scoped async session, auto-closing on exit."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
