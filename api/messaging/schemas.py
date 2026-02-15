"""
Messaging Domain — Pydantic Request / Response Schemas.

Contracts for sending messages and retrieving chat history.
Content is always returned decrypted to the client — encryption
is transparent to the API consumer.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Send Message ──────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    """Patient or professional sends a message within an appointment."""
    appointment_id: UUID
    content: str = Field(..., min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    """Single message (decrypted content returned to client)."""
    id: UUID
    appointment_id: UUID
    sender_id: UUID
    receiver_id: UUID
    content: str  # Decrypted plaintext
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Chat History ──────────────────────────────────────────────

class ChatHistoryResponse(BaseModel):
    """Chronological message thread for an appointment."""
    appointment_id: UUID
    messages: list[MessageResponse]
    total: int


# ── Unread Count ──────────────────────────────────────────────

class UnreadCountResponse(BaseModel):
    """Number of unread messages for the current user."""
    unread_count: int


# ── Mark Read ─────────────────────────────────────────────────

class MarkReadRequest(BaseModel):
    """Mark messages as read up to a certain point."""
    appointment_id: UUID
    up_to_message_id: UUID | None = Field(
        default=None,
        description="Mark all messages up to this ID as read. If null, marks all.",
    )


class MarkReadResponse(BaseModel):
    """Confirmation of read receipt update."""
    marked_count: int
    message: str
