"""
Marketplace Domain — Service Layer.

Business logic for profile management, search, and admin verification.
All queries are confined to the ProfessionalProfile table, with a join
to User for email data. Identity Agent owns user creation.
"""

import math
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.identity.models import User, UserRole
from api.marketplace.models import ProfessionalProfile
from api.marketplace.schemas import (
    ProfileCreateRequest,
    ProfileDetail,
    ProfilePublic,
    ProfileUpdateRequest,
    SearchQuery,
    SearchResponse,
    VerifyProfessionalResponse,
)


class MarketplaceService:
    """Stateless service — receives an async session per call."""

    # ── Profile CRUD ───────────────────────────────────────────

    @staticmethod
    async def create_profile(
        db: AsyncSession,
        user: User,
        payload: ProfileCreateRequest,
    ) -> ProfileDetail:
        """
        Create a professional profile for the authenticated user.

        Guards:
          - User must have role='professional'.
          - User must not already have a profile.
        """
        if user.role != UserRole.PROFESSIONAL:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only professionals can create a profile.",
            )

        # Check duplicate
        existing = await db.execute(
            select(ProfessionalProfile).where(
                ProfessionalProfile.user_id == user.id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Profile already exists. Use PATCH to update.",
            )

        profile = ProfessionalProfile(
            user_id=user.id,
            specialty=payload.specialty,
            sub_specialties=payload.sub_specialties,
            bio=payload.bio,
            license_number=payload.license_number,
            years_of_experience=payload.years_of_experience,
            consultation_fee=payload.consultation_fee,
            avatar_url=payload.avatar_url,
            is_verified=False,  # Requires admin approval
        )
        db.add(profile)
        await db.flush()

        return ProfileDetail(
            **_profile_to_dict(profile),
            email=user.email,
        )

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user: User,
        payload: ProfileUpdateRequest,
    ) -> ProfileDetail:
        """Partial update of the current user's profile."""
        result = await db.execute(
            select(ProfessionalProfile).where(
                ProfessionalProfile.user_id == user.id
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found. Create one first.",
            )

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)

        await db.flush()

        return ProfileDetail(
            **_profile_to_dict(profile),
            email=user.email,
        )

    @staticmethod
    async def get_profile_by_id(
        db: AsyncSession,
        profile_id: UUID,
    ) -> ProfilePublic:
        """Retrieve a single professional profile (public view)."""
        result = await db.execute(
            select(ProfessionalProfile, User.email)
            .join(User, ProfessionalProfile.user_id == User.id)
            .where(ProfessionalProfile.id == profile_id)
        )
        row = result.one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Professional not found.",
            )

        profile, email = row
        return ProfilePublic(**_profile_to_dict(profile), email=email)

    # ── Search ─────────────────────────────────────────────────

    @staticmethod
    async def search(
        db: AsyncSession,
        query: SearchQuery,
    ) -> SearchResponse:
        """
        Full-text search across verified professionals.

        Uses ILIKE for specialty/bio queries. Only verified professionals
        appear in results (data accuracy guarantee).
        """
        base = (
            select(ProfessionalProfile, User.email)
            .join(User, ProfessionalProfile.user_id == User.id)
            .where(ProfessionalProfile.is_verified == True)  # noqa: E712
            .where(User.is_active == True)  # noqa: E712
        )

        # Free-text search across specialty + bio
        if query.q:
            search_term = f"%{query.q}%"
            base = base.where(
                or_(
                    ProfessionalProfile.specialty.ilike(search_term),
                    ProfessionalProfile.sub_specialties.ilike(search_term),
                    ProfessionalProfile.bio.ilike(search_term),
                )
            )

        # Exact specialty filter
        if query.specialty:
            base = base.where(
                ProfessionalProfile.specialty.ilike(f"%{query.specialty}%")
            )

        # Rating floor
        if query.min_rating is not None:
            base = base.where(ProfessionalProfile.rating >= query.min_rating)

        # Fee ceiling
        if query.max_fee is not None:
            base = base.where(
                ProfessionalProfile.consultation_fee <= query.max_fee
            )

        # Count total before pagination
        count_q = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Paginate & order by rating desc
        offset = (query.page - 1) * query.page_size
        paginated = (
            base
            .order_by(ProfessionalProfile.rating.desc())
            .offset(offset)
            .limit(query.page_size)
        )

        rows = (await db.execute(paginated)).all()

        results = [
            ProfilePublic(**_profile_to_dict(profile), email=email)
            for profile, email in rows
        ]

        return SearchResponse(
            results=results,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=math.ceil(total / query.page_size) if total else 0,
        )

    # ── Admin: Verify Professional ─────────────────────────────

    @staticmethod
    async def verify_professional(
        db: AsyncSession,
        profile_id: UUID,
        is_verified: bool,
    ) -> VerifyProfessionalResponse:
        """
        Admin-only: toggle the is_verified flag on a professional profile.

        Guards: Only admins may call this (enforced at the router level).
        """
        result = await db.execute(
            select(ProfessionalProfile).where(
                ProfessionalProfile.id == profile_id
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Professional profile not found.",
            )

        profile.is_verified = is_verified
        await db.flush()

        action = "verified" if is_verified else "unverified"
        return VerifyProfessionalResponse(
            profile_id=profile.id,
            is_verified=profile.is_verified,
            message=f"Professional has been {action} successfully.",
        )


# ── Helper ─────────────────────────────────────────────────────

def _profile_to_dict(profile: ProfessionalProfile) -> dict:
    """Convert ORM instance to a dict for Pydantic model construction."""
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "specialty": profile.specialty,
        "sub_specialties": profile.sub_specialties,
        "bio": profile.bio,
        "license_number": profile.license_number,
        "years_of_experience": profile.years_of_experience,
        "consultation_fee": profile.consultation_fee,
        "is_verified": profile.is_verified,
        "avatar_url": profile.avatar_url,
        "rating": profile.rating,
        "review_count": profile.review_count,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }
