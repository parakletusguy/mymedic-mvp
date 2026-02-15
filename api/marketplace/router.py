"""
Marketplace Domain — API Router.

Endpoints:
    POST   /professionals/profile       — Create own profile (Professional).
    PATCH  /professionals/profile       — Update own profile (Professional).
    GET    /professionals/search        — Public paginated search.
    GET    /professionals/{id}          — Public profile detail.
    PATCH  /admin/verify-professional/{id} — Admin verify/reject a professional.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.identity.dependencies import get_current_active_user, require_role
from api.identity.models import User
from api.marketplace.schemas import (
    ProfileCreateRequest,
    ProfileDetail,
    ProfilePublic,
    ProfileUpdateRequest,
    SearchQuery,
    SearchResponse,
    VerifyProfessionalRequest,
    VerifyProfessionalResponse,
)
from api.marketplace.service import MarketplaceService

router = APIRouter(tags=["Marketplace"])


# ── Profile Management (Professional-only) ─────────────────────

@router.post(
    "/professionals/profile",
    response_model=ProfileDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a professional profile.",
)
async def create_profile(
    payload: ProfileCreateRequest,
    user: User = Depends(require_role("professional")),
    db: AsyncSession = Depends(get_db),
) -> ProfileDetail:
    """
    A professional creates their public-facing profile.
    Profile starts as **unverified** until an admin approves it.
    """
    return await MarketplaceService.create_profile(db, user, payload)


@router.patch(
    "/professionals/profile",
    response_model=ProfileDetail,
    summary="Update your professional profile.",
)
async def update_profile(
    payload: ProfileUpdateRequest,
    user: User = Depends(require_role("professional")),
    db: AsyncSession = Depends(get_db),
) -> ProfileDetail:
    """Partial update — only send the fields you want to change."""
    return await MarketplaceService.update_profile(db, user, payload)


# ── Public Discovery ───────────────────────────────────────────

@router.get(
    "/professionals/search",
    response_model=SearchResponse,
    summary="Search verified professionals.",
)
async def search_professionals(
    q: str | None = Query(default=None, description="Free-text search"),
    specialty: str | None = Query(default=None),
    min_rating: float | None = Query(default=None, ge=0.0, le=5.0),
    max_fee: float | None = Query(default=None, ge=0.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """
    Public endpoint — no auth required.

    Only **verified** and **active** professionals appear.
    Results are ordered by rating (descending).
    """
    query = SearchQuery(
        q=q,
        specialty=specialty,
        min_rating=min_rating,
        max_fee=max_fee,
        page=page,
        page_size=page_size,
    )
    return await MarketplaceService.search(db, query)


@router.get(
    "/professionals/{profile_id}",
    response_model=ProfilePublic,
    summary="Get a professional's public profile.",
)
async def get_professional(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ProfilePublic:
    """Public endpoint — returns a single professional's profile."""
    return await MarketplaceService.get_profile_by_id(db, profile_id)


# ── Admin: Verification ───────────────────────────────────────

@router.patch(
    "/admin/verify-professional/{profile_id}",
    response_model=VerifyProfessionalResponse,
    summary="Admin: Verify or reject a professional.",
)
async def verify_professional(
    profile_id: UUID,
    payload: VerifyProfessionalRequest,
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> VerifyProfessionalResponse:
    """
    Admin-only. Toggles the `is_verified` flag after license review.
    Only verified professionals appear in patient search results.
    """
    return await MarketplaceService.verify_professional(
        db, profile_id, payload.is_verified
    )
