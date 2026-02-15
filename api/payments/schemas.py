"""
Payments Domain — Pydantic Schemas.

Contracts for payment initialization, webhook events, and admin ledger.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Initialize Payment ─────────────────────────────────────────

class InitializePaymentRequest(BaseModel):
    """Patient initiates a payment for an appointment."""
    appointment_id: UUID
    callback_url: str = Field(
        default="https://mymedic.app/payment/callback",
        description="URL the gateway redirects to after payment.",
    )


class InitializePaymentResponse(BaseModel):
    """Returns the checkout URL for the patient to complete payment."""
    reference: str
    checkout_url: str
    amount: float
    currency: str
    message: str = "Redirect the patient to checkout_url to complete payment."


# ── Transaction Response ──────────────────────────────────────

class TransactionResponse(BaseModel):
    """Standard transaction record returned to clients."""
    id: UUID
    reference: str
    amount: float
    currency: str
    status: str
    provider: str
    user_id: UUID
    appointment_id: UUID | None
    professional_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Webhook Payload (Paystack format) ─────────────────────────

class PaystackWebhookEvent(BaseModel):
    """
    Paystack sends this JSON in the webhook POST body.
    We only process 'charge.success' events.
    """
    event: str
    data: dict


# ── Admin Ledger ──────────────────────────────────────────────

class ProfessionalEarnings(BaseModel):
    """Read-only earnings summary for a professional."""
    professional_id: UUID
    email: str
    total_earned: float
    currency: str
    transaction_count: int


class EarningsLedgerResponse(BaseModel):
    """Admin view of all professional earnings."""
    entries: list[ProfessionalEarnings]
    total_platform_revenue: float
    currency: str


# ── Payment Verification ──────────────────────────────────────

class VerifyPaymentResponse(BaseModel):
    """Result of manual payment verification."""
    reference: str
    status: str
    amount: float
    message: str
