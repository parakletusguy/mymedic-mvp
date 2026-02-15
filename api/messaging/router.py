"""
Messaging Domain — API Router.

Endpoints:
    POST  /chat/send                      — Send an encrypted message.
    GET   /chat/history/{appointment_id}   — Get decrypted chat thread.
    GET   /chat/unread                     — Unread message count.
    POST  /chat/read                       — Mark messages as read.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.identity.dependencies import get_current_active_user
from api.identity.models import User
from api.messaging.schemas import (
    ChatHistoryResponse,
    MarkReadRequest,
    MarkReadResponse,
    MessageResponse,
    SendMessageRequest,
    UnreadCountResponse,
)
from api.messaging.service import MessagingService

router = APIRouter(prefix="/chat", tags=["Secure Messaging"])


# ── Send Message ──────────────────────────────────────────────

@router.post(
    "/send",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message within a confirmed appointment.",
)
async def send_message(
    payload: SendMessageRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    **Gatekeeper enforced**: Sender must be a party to a CONFIRMED
    appointment. Content is encrypted at rest with Fernet.
    """
    return await MessagingService.send_message(db, user, payload)


# ── Chat History ──────────────────────────────────────────────

@router.get(
    "/history/{appointment_id}",
    response_model=ChatHistoryResponse,
    summary="Get chat history for an appointment.",
)
async def get_chat_history(
    appointment_id: UUID,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """
    **Gatekeeper enforced**: Only parties to the appointment can
    read the chat thread. Content is decrypted on the fly.
    """
    return await MessagingService.get_chat_history(db, user, appointment_id)


# ── Unread Count ──────────────────────────────────────────────

@router.get(
    "/unread",
    response_model=UnreadCountResponse,
    summary="Get unread message count.",
)
async def unread_count(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Returns the total number of unread messages across all chats."""
    return await MessagingService.get_unread_count(db, user)


# ── Mark as Read ──────────────────────────────────────────────

@router.post(
    "/read",
    response_model=MarkReadResponse,
    summary="Mark messages as read.",
)
async def mark_read(
    payload: MarkReadRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MarkReadResponse:
    """
    Marks messages as read for the current user in the given appointment.
    Optionally specify `up_to_message_id` to mark only messages up to that point.
    """
    return await MessagingService.mark_as_read(
        db, user, payload.appointment_id, payload.up_to_message_id
    )
