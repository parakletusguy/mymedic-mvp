"""
Marketplace Domain — Pydantic Request / Response Schemas.

Strict contracts for profile management, search, and admin verification.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Profile Creation / Update ──────────────────────────────────

class ProfileCreateRequest(BaseModel):
    """Payload for a professional setting up their profile."""
    specialty: str = Field(..., min_length=2, max_length=100)
    sub_specialties: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=2000)
    license_number: str = Field(..., min_length=3, max_length=100)
    years_of_experience: int = Field(default=0, ge=0)
    consultation_fee: float = Field(default=0.0, ge=0.0)
    avatar_url: str | None = None


class ProfileUpdateRequest(BaseModel):
    """Partial update — all fields optional."""
    specialty: str | None = Field(default=None, min_length=2, max_length=100)
    sub_specialties: str | None = Field(default=None, max_length=500)
    bio: str | None = Field(default=None, max_length=2000)
    license_number: str | None = Field(default=None, min_length=3, max_length=100)
    years_of_experience: int | None = Field(default=None, ge=0)
    consultation_fee: float | None = Field(default=None, ge=0.0)
    avatar_url: str | None = None


# ── Profile Response (Public) ──────────────────────────────────

class ProfilePublic(BaseModel):
    """Safe profile representation for search results and detail pages."""
    id: UUID
    user_id: UUID
    specialty: str
    sub_specialties: str | None
    bio: str | None
    years_of_experience: int
    consultation_fee: float
    is_verified: bool
    avatar_url: str | None
    rating: float
    review_count: int
    created_at: datetime

    # Joined user fields (populated in service layer)
    email: str | None = None
    name: str | None = None

    model_config = {"from_attributes": True}


class ProfileDetail(ProfilePublic):
    """Extended detail view including license (for admin/self)."""
    license_number: str
    updated_at: datetime


# ── Search ─────────────────────────────────────────────────────

class SearchQuery(BaseModel):
    """Query parameters for professional search."""
    q: str | None = Field(default=None, description="Free-text search (specialty, bio)")
    specialty: str | None = Field(default=None, description="Exact specialty filter")
    min_rating: float | None = Field(default=None, ge=0.0, le=5.0)
    max_fee: float | None = Field(default=None, ge=0.0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SearchResponse(BaseModel):
    """Paginated search results."""
    results: list[ProfilePublic]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Admin Verification ─────────────────────────────────────────

class VerifyProfessionalRequest(BaseModel):
    """Admin action to verify or reject a professional."""
    is_verified: bool


class VerifyProfessionalResponse(BaseModel):
    """Confirmation of verification status change."""
    profile_id: UUID
    is_verified: bool
    message: str
