"""
Messaging Domain — SQL Models.

Message stores encrypted chat content between a patient and a
professional, scoped to a CONFIRMED appointment.

SECURITY:
  - Message content is encrypted at rest using Fernet symmetric encryption.
  - The encryption key is derived from the application's JWT secret.
  - Only parties to a CONFIRMED appointment can send/read messages.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Message(Base):
    """
    Encrypted chat message between patient and professional.

    Fields
    ------
    id : UUID               Primary key.
    appointment_id : UUID    FK → appointments.id (scoping boundary).
    sender_id : UUID         FK → users.id (who sent the message).
    receiver_id : UUID       FK → users.id (who receives the message).
    content_encrypted : str  Fernet-encrypted message body.
    is_read : bool           Read receipt flag.
    created_at : datetime    Timestamp (UTC).
    """

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    receiver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_msg_appointment_time", "appointment_id", "created_at"),
        Index("ix_msg_receiver_unread", "receiver_id", "is_read"),
    )

    sender = relationship("User", foreign_keys=[sender_id], backref="messages_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], backref="messages_received")
    appointment = relationship("Appointment", backref="messages", lazy="joined")

    def __repr__(self) -> str:
        return f"<Message {self.sender_id} → {self.receiver_id} @ {self.created_at}>"
