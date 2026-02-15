"""
MyMedic — FastAPI Application Entry Point.

Assembles routers from all domain agents into a single Modular Monolith.
New agents simply register their router here.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import settings
from api.core.database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    # Create tables (dev only — use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="HIPAA-compliant Healthcare MVP — Telemedicine & Booking",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# ── CORS (restrict in production) ──────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Domain Routers ───────────────────────────────────
from api.identity.router import router as identity_router  # noqa: E402

app.include_router(identity_router, prefix=settings.api_v1_prefix)

from api.marketplace.router import router as marketplace_router  # noqa: E402

app.include_router(marketplace_router, prefix=settings.api_v1_prefix)

# Future agents will add their routers here:
from api.booking.router import router as booking_router  # noqa: E402

app.include_router(booking_router, prefix=settings.api_v1_prefix)

from api.payments.router import router as payments_router  # noqa: E402

app.include_router(payments_router, prefix=settings.api_v1_prefix)

from api.messaging.router import router as messaging_router  # noqa: E402

app.include_router(messaging_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Infrastructure"])
async def health():
    """Simple health check for load balancers / monitoring."""
    return {"status": "healthy", "service": settings.app_name}
