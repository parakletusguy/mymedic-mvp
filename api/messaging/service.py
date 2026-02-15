"""
Messaging Domain — Service Layer.

Core responsibility: GATEKEEPER — no message is sent or read unless
the sender and receiver share a CONFIRMED appointment.

Security layers:
  1. Gatekeeper  — validates appointment relationship.
  2. Encryption  — Fernet encrypts content before DB write.
  3. Decryption  — Content is decrypted only on read, never stored plain.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.booking.models import Appointment, AppointmentStatus
from api.identity.models import User
from api.messaging.encryption import decrypt_message, encrypt_message
from api.messaging.models import Message
from api.messaging.schemas import (
    ChatHistoryResponse,
    MarkReadResponse,
    MessageResponse,
    SendMessageRequest,
    UnreadCountResponse,
)


class MessagingService:
    """Stateless service — receives an async session per call."""

    # ═══════════════════════════════════════════════════════════
    # GATEKEEPER — the core security check
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def _gatekeeper(
        db: AsyncSession,
        user: User,
        appointment_id: UUID,
    ) -> Appointment:
        """
        Verify the user is a party to a CONFIRMED appointment.

        Returns the Appointment if valid, raises 403 otherwise.
        This is called before EVERY send and read operation.
        """
        result = await db.execute(
            select(Appointment).where(Appointment.id == appointment_id)
        )
        appointment = result.scalar_one_or_none()

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found.",
            )

        # Must be a party to this appointment
        is_patient = appointment.patient_id == user.id
        is_professional = appointment.professional_id == user.id

        if not is_patient and not is_professional:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a party to this appointment.",
            )

        # Must be CONFIRMED or COMPLETED (allow history access after completion)
        if appointment.status not in (
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.COMPLETED,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Messaging requires a CONFIRMED appointment. "
                       f"Current status: {appointment.status.value}.",
            )

        return appointment

    # ═══════════════════════════════════════════════════════════
    # SEND MESSAGE
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def send_message(
        db: AsyncSession,
        user: User,
        payload: SendMessageRequest,
    ) -> MessageResponse:
        """
        Send an encrypted message within a confirmed appointment.

        Steps:
          1. Gatekeeper check (appointment exists, user is party, CONFIRMED).
          2. Determine receiver (the other party).
          3. Encrypt content with Fernet.
          4. Persist encrypted message.
          5. Return decrypted response.
        """
        appointment = await MessagingService._gatekeeper(
            db, user, payload.appointment_id
        )

        # Determine receiver
        if appointment.patient_id == user.id:
            receiver_id = appointment.professional_id
        else:
            receiver_id = appointment.patient_id

        # Encrypt content
        encrypted = encrypt_message(payload.content)

        message = Message(
            appointment_id=appointment.id,
            sender_id=user.id,
            receiver_id=receiver_id,
            content_encrypted=encrypted,
        )
        db.add(message)
        await db.flush()

        return MessageResponse(
            id=message.id,
            appointment_id=message.appointment_id,
            sender_id=message.sender_id,
            receiver_id=message.receiver_id,
            content=payload.content,  # Return plaintext to sender
            is_read=False,
            created_at=message.created_at,
        )

    # ═══════════════════════════════════════════════════════════
    # CHAT HISTORY
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def get_chat_history(
        db: AsyncSession,
        user: User,
        appointment_id: UUID,
    ) -> ChatHistoryResponse:
        """
        Retrieve the full decrypted chat thread for an appointment.

        Gatekeeper ensures only authorized parties can read.
        """
        await MessagingService._gatekeeper(db, user, appointment_id)

        result = await db.execute(
            select(Message)
            .where(Message.appointment_id == appointment_id)
            .order_by(Message.created_at.asc())
        )
        rows = result.scalars().all()

        messages = []
        for msg in rows:
            try:
                content = decrypt_message(msg.content_encrypted)
            except Exception:
                content = "[Unable to decrypt message]"

            messages.append(MessageResponse(
                id=msg.id,
                appointment_id=msg.appointment_id,
                sender_id=msg.sender_id,
                receiver_id=msg.receiver_id,
                content=content,
                is_read=msg.is_read,
                created_at=msg.created_at,
            ))

        return ChatHistoryResponse(
            appointment_id=appointment_id,
            messages=messages,
            total=len(messages),
        )

    # ═══════════════════════════════════════════════════════════
    # UNREAD COUNT
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        user: User,
    ) -> UnreadCountResponse:
        """Count all unread messages for the current user."""
        result = await db.execute(
            select(func.count()).where(
                Message.receiver_id == user.id,
                Message.is_read == False,  # noqa: E712
            )
        )
        count = result.scalar() or 0
        return UnreadCountResponse(unread_count=count)

    # ═══════════════════════════════════════════════════════════
    # MARK AS READ
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        user: User,
        appointment_id: UUID,
        up_to_message_id: UUID | None = None,
    ) -> MarkReadResponse:
        """
        Mark messages as read for the current user in an appointment.

        Only marks messages where the user is the RECEIVER.
        """
        await MessagingService._gatekeeper(db, user, appointment_id)

        query = (
            update(Message)
            .where(
                Message.appointment_id == appointment_id,
                Message.receiver_id == user.id,
                Message.is_read == False,  # noqa: E712
            )
        )

        if up_to_message_id:
            # Get the cutoff timestamp
            cutoff_result = await db.execute(
                select(Message.created_at).where(Message.id == up_to_message_id)
            )
            cutoff_time = cutoff_result.scalar_one_or_none()
            if cutoff_time:
                query = query.where(Message.created_at <= cutoff_time)

        query = query.values(is_read=True)
        result = await db.execute(query)
        marked = result.rowcount

        await db.flush()

        return MarkReadResponse(
            marked_count=marked,
            message=f"{marked} message(s) marked as read.",
        )
