"""
Payments Domain — Service Layer.

Transaction lifecycle:
  1. Initialize  → Create PENDING transaction, get checkout URL.
  2. Webhook     → Gateway POSTs charge.success → verify signature → mark SUCCESS.
  3. Verify      → Manual verification endpoint (backup for webhooks).
  4. Ledger      → Admin-only aggregated earnings per professional.

CRITICAL:
  - Webhook signature is verified BEFORE any DB writes.
  - Double-processing is prevented via idempotent reference checks.
  - On SUCCESS, the linked Appointment can be confirmed automatically.
"""

import json
import uuid
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Appointment, AppointmentStatus
from api.identity.models import User
from api.marketplace.models import ProfessionalProfile
from api.payments.gateway import paystack_client
from api.payments.models import (
    PaymentProvider,
    Transaction,
    TransactionStatus,
)
from api.payments.schemas import (
    EarningsLedgerResponse,
    InitializePaymentRequest,
    InitializePaymentResponse,
    ProfessionalEarnings,
    TransactionResponse,
    VerifyPaymentResponse,
)


class PaymentService:
    """Stateless service — receives an async session per call."""

    # ═══════════════════════════════════════════════════════════
    # INITIALIZE PAYMENT
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def initialize_payment(
        db: AsyncSession,
        patient: User,
        payload: InitializePaymentRequest,
    ) -> InitializePaymentResponse:
        """
        Create a PENDING transaction and return a checkout URL.

        Steps:
          1. Validate the appointment exists and belongs to this patient.
          2. Fetch the professional's consultation fee.
          3. Check for duplicate pending transactions.
          4. Call Paystack to get checkout URL.
          5. Persist the Transaction record.
        """
        # ── Step 1: Validate appointment ───────────────────────
        result = await db.execute(
            select(Appointment).where(Appointment.id == payload.appointment_id)
        )
        appointment = result.scalar_one_or_none()

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )
        if appointment.patient_id != patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This appointment does not belong to you.",
            )
        if appointment.status not in (
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot pay for an appointment with status '{appointment.status.value}'.",
            )

        # ── Step 2: Get consultation fee ───────────────────────
        profile_result = await db.execute(
            select(ProfessionalProfile).where(
                ProfessionalProfile.user_id == appointment.professional_id
            )
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Professional profile not found. Cannot determine fee.",
            )

        amount_naira = profile.consultation_fee
        amount_kobo = int(amount_naira * 100)  # Paystack uses kobo

        if amount_kobo <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Professional has not set a consultation fee.",
            )

        # ── Step 3: Prevent duplicate pending payments ─────────
        existing = await db.execute(
            select(Transaction).where(
                Transaction.appointment_id == payload.appointment_id,
                Transaction.status == TransactionStatus.PENDING,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending payment already exists for this appointment.",
            )

        # ── Step 4: Call Paystack ──────────────────────────────
        reference = f"mymedic_{uuid.uuid4().hex[:16]}"

        gateway_data = await paystack_client.initialize_transaction(
            email=patient.email,
            amount_kobo=amount_kobo,
            reference=reference,
            callback_url=payload.callback_url,
            metadata={
                "appointment_id": str(appointment.id),
                "patient_id": str(patient.id),
                "professional_id": str(appointment.professional_id),
            },
        )

        # ── Step 5: Persist transaction ────────────────────────
        txn = Transaction(
            reference=reference,
            amount=amount_naira,
            currency="NGN",
            status=TransactionStatus.PENDING,
            provider=PaymentProvider.PAYSTACK if not paystack_client.is_mock else PaymentProvider.MOCK,
            user_id=patient.id,
            appointment_id=appointment.id,
            professional_id=appointment.professional_id,
            checkout_url=gateway_data.get("authorization_url", ""),
            metadata_json=json.dumps(gateway_data),
        )
        db.add(txn)
        await db.flush()

        return InitializePaymentResponse(
            reference=reference,
            checkout_url=gateway_data["authorization_url"],
            amount=amount_naira,
            currency="NGN",
        )

    # ═══════════════════════════════════════════════════════════
    # WEBHOOK HANDLER (Paystack)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def handle_webhook(
        db: AsyncSession,
        event_type: str,
        event_data: dict,
    ) -> dict:
        """
        Process a Paystack webhook event.

        Only 'charge.success' events are processed.
        Idempotent: if the transaction is already SUCCESS, skip.
        """
        if event_type != "charge.success":
            return {"status": "ignored", "reason": f"Event '{event_type}' not handled."}

        reference = event_data.get("reference")
        if not reference:
            return {"status": "error", "reason": "No reference in event data."}

        # Find the transaction
        result = await db.execute(
            select(Transaction).where(Transaction.reference == reference)
        )
        txn = result.scalar_one_or_none()

        if not txn:
            return {"status": "error", "reason": f"Transaction {reference} not found."}

        # Idempotent check
        if txn.status == TransactionStatus.SUCCESS:
            return {"status": "already_processed", "reference": reference}

        # Mark as SUCCESS
        txn.status = TransactionStatus.SUCCESS
        txn.provider_reference = event_data.get("id", "")
        txn.metadata_json = json.dumps(event_data)

        # ── Auto-confirm appointment if still PENDING ──────────
        if txn.appointment_id:
            appt_result = await db.execute(
                select(Appointment).where(Appointment.id == txn.appointment_id)
            )
            appt = appt_result.scalar_one_or_none()
            if appt and appt.status == AppointmentStatus.PENDING:
                appt.status = AppointmentStatus.CONFIRMED

        await db.flush()

        return {"status": "success", "reference": reference}

    # ═══════════════════════════════════════════════════════════
    # VERIFY PAYMENT (Manual backup)
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def verify_payment(
        db: AsyncSession,
        reference: str,
    ) -> VerifyPaymentResponse:
        """
        Manually verify a payment via the Paystack API.
        Used as a backup when webhooks are delayed.
        """
        result = await db.execute(
            select(Transaction).where(Transaction.reference == reference)
        )
        txn = result.scalar_one_or_none()
        if not txn:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found.",
            )

        # Already settled
        if txn.status == TransactionStatus.SUCCESS:
            return VerifyPaymentResponse(
                reference=reference,
                status="success",
                amount=txn.amount,
                message="Transaction already verified.",
            )

        # Call Paystack verify endpoint
        gateway_data = await paystack_client.verify_transaction(reference)
        gateway_status = gateway_data.get("status", "")

        if gateway_status == "success":
            txn.status = TransactionStatus.SUCCESS
            txn.provider_reference = str(gateway_data.get("id", ""))
            txn.metadata_json = json.dumps(gateway_data)

            # Auto-confirm appointment
            if txn.appointment_id:
                appt_result = await db.execute(
                    select(Appointment).where(Appointment.id == txn.appointment_id)
                )
                appt = appt_result.scalar_one_or_none()
                if appt and appt.status == AppointmentStatus.PENDING:
                    appt.status = AppointmentStatus.CONFIRMED

            await db.flush()

            return VerifyPaymentResponse(
                reference=reference,
                status="success",
                amount=txn.amount,
                message="Payment verified and confirmed.",
            )
        else:
            txn.status = TransactionStatus.FAILED
            await db.flush()

            return VerifyPaymentResponse(
                reference=reference,
                status="failed",
                amount=txn.amount,
                message=f"Gateway status: {gateway_status}",
            )

    # ═══════════════════════════════════════════════════════════
    # TRANSACTION HISTORY
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def get_user_transactions(
        db: AsyncSession,
        user: User,
    ) -> list[TransactionResponse]:
        """Get all transactions for the current user."""
        result = await db.execute(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.created_at.desc())
        )
        rows = result.scalars().all()
        return [TransactionResponse.model_validate(r) for r in rows]

    # ═══════════════════════════════════════════════════════════
    # ADMIN: EARNINGS LEDGER
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def get_earnings_ledger(
        db: AsyncSession,
    ) -> EarningsLedgerResponse:
        """
        Admin-only: Aggregated earnings per professional.

        Sums all SUCCESS transactions grouped by professional_id.
        """
        result = await db.execute(
            select(
                Transaction.professional_id,
                User.email,
                func.sum(Transaction.amount).label("total_earned"),
                func.count(Transaction.id).label("txn_count"),
            )
            .join(User, Transaction.professional_id == User.id)
            .where(Transaction.status == TransactionStatus.SUCCESS)
            .group_by(Transaction.professional_id, User.email)
            .order_by(func.sum(Transaction.amount).desc())
        )
        rows = result.all()

        entries = [
            ProfessionalEarnings(
                professional_id=row.professional_id,
                email=row.email,
                total_earned=float(row.total_earned or 0),
                currency="NGN",
                transaction_count=row.txn_count,
            )
            for row in rows
        ]

        total_revenue = sum(e.total_earned for e in entries)

        return EarningsLedgerResponse(
            entries=entries,
            total_platform_revenue=total_revenue,
            currency="NGN",
        )
