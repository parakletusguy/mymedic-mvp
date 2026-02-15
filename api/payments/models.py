"""
Payments Domain — SQL Models.

Transaction is the single source of truth for payment state.
It references both the paying user and the appointment being paid for.

SECURITY: Raw card details are NEVER stored. All card handling is
delegated to the payment gateway (Paystack/Flutterwave).
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class TransactionStatus(str, enum.Enum):
    """Payment state machine: PENDING → SUCCESS | FAILED | REFUNDED."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentProvider(str, enum.Enum):
    """Supported payment gateways."""
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    MOCK = "mock"  # Test environment


class Transaction(Base):
    """
    Immutable payment record.

    Fields
    ------
    id : UUID               Primary key.
    reference : str          Unique transaction reference (provider-facing).
    provider_reference : str Gateway's own reference (from webhook).
    amount : float           Amount in minor units (kobo/cents) stored as float.
    currency : str           ISO 4217 (NGN, USD, etc.).
    status : TransactionStatus
    provider : PaymentProvider
    user_id : UUID           FK → users.id (the payer / patient).
    appointment_id : UUID    FK → appointments.id (nullable for top-ups).
    professional_id : UUID   FK → users.id (the payee / professional).
    checkout_url : str       Redirect URL from the gateway.
    metadata_json : str      Raw JSON from gateway (for audit trail).
    """

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    reference: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
    )
    provider_reference: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    amount: Mapped[float] = mapped_column(
        Float, nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3), default="NGN", nullable=False,
    )
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, name="transaction_status", create_constraint=True),
        default=TransactionStatus.PENDING,
        nullable=False,
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        SAEnum(PaymentProvider, name="payment_provider", create_constraint=True),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    professional_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    checkout_url: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_txn_user_status", "user_id", "status"),
        Index("ix_txn_professional", "professional_id"),
    )

    payer = relationship("User", foreign_keys=[user_id], backref="payments_made")
    payee = relationship("User", foreign_keys=[professional_id], backref="payments_received")
    appointment = relationship("Appointment", backref="transaction", lazy="joined")

    def __repr__(self) -> str:
        return f"<Transaction {self.reference} {self.status.value} {self.amount} {self.currency}>"
