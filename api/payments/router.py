"""
Payments Domain — API Router.

Endpoints:
    POST  /payments/initialize        — Start a payment (Patient).
    POST  /payments/webhook/paystack  — Paystack webhook receiver.
    GET   /payments/verify/{ref}      — Manual payment verification.
    GET   /payments/history           — User's transaction history.
    GET   /admin/earnings             — Admin: professional earnings ledger.
"""

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.identity.dependencies import get_current_active_user, require_role
from api.identity.models import User
from api.payments.gateway import paystack_client
from api.payments.schemas import (
    EarningsLedgerResponse,
    InitializePaymentRequest,
    InitializePaymentResponse,
    TransactionResponse,
    VerifyPaymentResponse,
)
from api.payments.service import PaymentService

router = APIRouter(tags=["Payments"])


# ── Initialize Payment (Patient) ──────────────────────────────

@router.post(
    "/payments/initialize",
    response_model=InitializePaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize a payment for an appointment.",
)
async def initialize_payment(
    payload: InitializePaymentRequest,
    user: User = Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
) -> InitializePaymentResponse:
    """
    Creates a PENDING transaction and returns a Paystack checkout URL.
    The patient must be redirected to this URL to complete payment.
    """
    return await PaymentService.initialize_payment(db, user, payload)


# ── Paystack Webhook ──────────────────────────────────────────

@router.post(
    "/payments/webhook/paystack",
    status_code=status.HTTP_200_OK,
    summary="Paystack webhook receiver (server-to-server).",
)
async def paystack_webhook(
    request: Request,
    x_paystack_signature: str = Header(default="", alias="x-paystack-signature"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Receives Paystack webhook events.

    SECURITY:
      1. Reads raw body for HMAC-SHA512 signature verification.
      2. Only processes 'charge.success' events.
      3. Idempotent — re-processing the same event is safe.
    """
    body = await request.body()

    # Verify signature (CRITICAL — prevents forged webhooks)
    if not paystack_client.verify_webhook_signature(body, x_paystack_signature):
        return {"status": "error", "reason": "Invalid signature."}

    payload = await request.json()
    event_type = payload.get("event", "")
    event_data = payload.get("data", {})

    return await PaymentService.handle_webhook(db, event_type, event_data)


# ── Manual Verification ───────────────────────────────────────

@router.get(
    "/payments/verify/{reference}",
    response_model=VerifyPaymentResponse,
    summary="Manually verify a payment by reference.",
)
async def verify_payment(
    reference: str,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyPaymentResponse:
    """
    Backup for webhook delivery failures.
    Calls the Paystack verify API directly.
    """
    return await PaymentService.verify_payment(db, reference)


# ── Transaction History ───────────────────────────────────────

@router.get(
    "/payments/history",
    response_model=list[TransactionResponse],
    summary="Your payment history.",
)
async def payment_history(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransactionResponse]:
    """Returns all transactions for the authenticated user."""
    return await PaymentService.get_user_transactions(db, user)


# ── Admin: Earnings Ledger ────────────────────────────────────

@router.get(
    "/admin/earnings",
    response_model=EarningsLedgerResponse,
    summary="Admin: View professional earnings ledger.",
)
async def earnings_ledger(
    _admin: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> EarningsLedgerResponse:
    """
    Admin-only. Read-only aggregated earnings per professional.
    Sums all SUCCESS transactions grouped by professional_id.
    """
    return await PaymentService.get_earnings_ledger(db)
